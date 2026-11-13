"""Phase 0 checks run inside the container with `docker exec`, plus two throwaway runs.

Covers the firewall from the guest's side (check 11, with a no-firewall
baseline container so the targets are shown to be reachable otherwise), the
rules and backend, IPv6 (13), the process tree and capabilities (part of 10),
PR_SET_DUMPABLE, Edge's environment, listeners, Edge's stderr, and that a bad
SIGNAL_BLOCK_CIDRS kills the container before the relay starts.
"""

import json
import secrets
from pathlib import Path

import docker_job
from results import Result

PROBES_DIR = Path(__file__).resolve().parent
CONNECT_SCRIPT = (PROBES_DIR / "guest_connect.py").read_text(encoding="utf-8")
PROCS_SCRIPT = (PROBES_DIR / "guest_procs.py").read_text(encoding="utf-8")
# Each blocked target is meant to have a listener behind it on the host (the
# whiteboard daemon :8770 on loopback, some local service on :1234 on 0.0.0.0),
# so the baseline shows real reach.
FIXED_BLOCKED_TARGETS = [
    "host.docker.internal:8770",
    "192.168.65.254:8770",
    "192-168-65-254.sslip.io:8770",
    "192.168.65.7:80",
    "172.17.0.1:80",
    "10.0.0.1:80",
    "192.168.1.1:80",
    "169.254.169.254:80",
    "100.64.0.1:80",
]
OPEN_TARGETS = ["example.com:443", "github.com:443"]
NO_CAPS = "0000000000000000"
SANDBOX_TROUBLE = ("EPERM", "SIGSYS", "Operation not permitted", "No usable sandbox", "seccomp")
BAD_BLOCK_LISTS = ["", "10.0.0.0/8,evil.example.com", "10.0.0.1/8"]


def check_firewall(job: docker_job.Job, host_ips: list[str]) -> Result:
    """11 (guest part): blocked targets are refused, the internet and DNS still work."""
    nameserver = _resolv_nameserver(job)
    blocked = [*FIXED_BLOCKED_TARGETS, *(f"{address}:1234" for address in host_ips)]
    allowed = [*OPEN_TARGETS, f"{nameserver}:53"]
    baseline = _connects(None, [*blocked, *allowed])
    guarded = _connects(job.name, [*blocked, *allowed])
    passed = all(guarded[t] == "refused" for t in blocked) and all(
        guarded[t] == "connected" for t in allowed
    )
    rows = [f"{t} {baseline[t]} -> {guarded[t]}" for t in [*blocked, *allowed]]
    return Result("11 firewall from the guest (no firewall -> firewall)", passed, "; ".join(rows))


def check_rules(job: docker_job.Job) -> Result:
    """11 (rules part): the backend in use, REJECT present, ip6tables policy DROP."""
    rules = docker_job.docker("exec", job.name, "iptables", "-S", "OUTPUT").stdout
    rules6 = docker_job.docker("exec", job.name, "ip6tables", "-S", "OUTPUT").stdout
    version = docker_job.docker("exec", job.name, "iptables", "-V").stdout.strip()
    passed = "-j REJECT" in rules and "-P OUTPUT DROP" in rules6
    detail = f"{version}; {rules.count('-j REJECT')} REJECT rules; ip6 {rules6.split()[:3]}"
    return Result("11 iptables rules", passed, detail)


def check_ipv6(job: docker_job.Job) -> Result:
    """13: no global IPv6 address inside the container."""
    output = docker_job.docker("exec", job.name, "ip", "-6", "addr").stdout
    return Result(
        "13 no global IPv6", "scope global" not in output, f"ip -6 addr: {output.strip()!r}"
    )


def check_processes(job: docker_job.Job) -> tuple[Result, list[dict[str, str]]]:
    """10 (process part): only docker-init is root; the rest are edge, no caps, no_new_privs.

    Capabilities count only in the container's user namespace: Chromium's
    sandbox zygote holds CAP_SYS_ADMIN inside the user namespace it created.
    """
    processes = _processes(job)
    others = [p for p in processes if p["pid"] != "1"]
    bad = [
        p
        for p in others
        if (p["Uid"], p["NoNewPrivs"], p["Seccomp"]) != ("1000", "1", "2")
        or (p["CapEff"] != NO_CAPS and p["userns"] != "other")
    ]
    pid1 = next((p for p in processes if p["pid"] == "1"), {})
    names = sorted({p["Name"] for p in others})
    sandboxed = [p["pid"] for p in others if p["userns"] == "other"]
    namespaced_caps = [(p["pid"], p["CapEff"]) for p in others if p["CapEff"] != NO_CAPS]
    detail = (
        f"PID 1 {pid1.get('Name')} uid {pid1.get('Uid')} caps {pid1.get('CapEff')}; "
        f"others {names}; in Chromium's sandbox userns {sandboxed}, "
        f"caps there {namespaced_caps}; violations {bad}"
    )
    return Result("10 process tree as edge", not bad, detail), processes


def check_dumpable(job: docker_job.Job, processes: list[dict[str, str]]) -> Result:
    """PR_SET_DUMPABLE: the relay's environ is unreadable; Edge's holds no SIGNAL_ variable."""
    relay = next(p for p in processes if "main.py" in p["cmd"])
    edge = next(p for p in processes if p["Name"] == "msedge" and "--type=" not in p["cmd"])
    as_edge = _read_environ(job, relay["pid"], user="edge")
    as_root = _read_environ(job, relay["pid"], user="root")
    edge_env = _read_environ(job, edge["pid"], user="edge")
    edge_keys = (
        sorted(item.split("=")[0] for item in edge_env.split("\0") if item) if edge_env else []
    )
    passed = as_edge is None and edge_env is not None and not any("SIGNAL" in k for k in edge_keys)
    detail = (
        f"relay environ as edge: {'denied' if as_edge is None else 'READABLE'}, "
        f"as container root: {'denied' if as_root is None else 'READABLE'}; "
        f"Edge env keys {edge_keys}"
    )
    return Result("PR_SET_DUMPABLE + Edge env", passed, detail)


def check_listeners(job: docker_job.Job) -> Result:
    """Only the relay and Edge's loopback CDP port listen on TCP."""
    output = docker_job.docker("exec", job.name, "ss", "-ltnH").stdout
    listening = sorted(line.split()[3] for line in output.splitlines() if line.strip())
    passed = set(listening) == {"0.0.0.0:9333", "127.0.0.1:9222"}
    return Result("TCP listeners", passed, f"{listening}")


def check_edge_stderr(job: docker_job.Job) -> Result:
    """10 (log part): no EPERM, SIGSYS or sandbox failure in Edge's stderr."""
    logs = docker_job.docker("logs", job.name, check=False)
    lines = (logs.stdout + logs.stderr).splitlines()
    trouble = [line for line in lines if any(word in line for word in SANDBOX_TROUBLE)]
    return Result(
        "10 Edge stderr clean", not trouble, f"{len(lines)} log lines; matches {trouble[:5]}"
    )


def check_bad_block_lists() -> Result:
    """A bad or empty SIGNAL_BLOCK_CIDRS ends the container before the relay starts."""
    outcomes = []
    for index, block_list in enumerate(BAD_BLOCK_LISTS):
        name = f"signal-browser-spike-badlist{index}"
        env = docker_job.job_environment(secrets.token_urlsafe(32), "", block_list)
        run = docker_job.docker(
            "run", *docker_job.run_arguments(name, "badlist"), env=env, check=False
        )
        output = run.stdout + run.stderr
        outcomes.append(
            (block_list, run.returncode, "relay listening" in output, output.strip()[-90:])
        )
    passed = all(code != 0 and not relay_up for _, code, relay_up, _ in outcomes)
    return Result("bad SIGNAL_BLOCK_CIDRS exits", passed, f"{outcomes}")


def _connects(container: str | None, targets: list[str]) -> dict[str, str]:
    """Run guest_connect.py in `container`, or in a no-firewall baseline container if None."""
    if container is None:
        prefix = [
            "run",
            "--rm",
            "-i",
            "--cap-drop=ALL",
            "--entrypoint",
            "python3",
            docker_job.IMAGE,
        ]
    else:
        prefix = ["exec", "-i", "-u", "edge", container, "python3"]
    output = docker_job.docker(*prefix, "-I", "-", *targets, stdin_text=CONNECT_SCRIPT).stdout
    rows = [json.loads(line) for line in output.splitlines()]
    return {row["target"]: row["result"] for row in rows}


def _processes(job: docker_job.Job) -> list[dict[str, str]]:
    output = docker_job.docker(
        "exec", "-i", "-u", "edge", job.name, "python3", "-I", "-", stdin_text=PROCS_SCRIPT
    ).stdout
    return [json.loads(line) for line in output.splitlines()]


def _read_environ(job: docker_job.Job, pid: str, user: str) -> str | None:
    """The process's /proc environ as `user` sees it, or None if reading it fails."""
    run = docker_job.docker(
        "exec", "-u", user, job.name, "cat", f"/proc/{pid}/environ", check=False
    )
    return run.stdout if run.returncode == 0 else None


def _resolv_nameserver(job: docker_job.Job) -> str:
    resolv = docker_job.docker("exec", job.name, "cat", "/etc/resolv.conf").stdout
    return next(line.split()[1] for line in resolv.splitlines() if line.startswith("nameserver"))
