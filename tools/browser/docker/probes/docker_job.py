"""Host-side helpers for the phase 0 probes: run docker, start a browser job, wait for it.

Prototype of what phase 1's `backends/docker_box.py` will do
(refdocs/research/docker-browser.md section 2): build the run line, pass the token
through the docker process's environment, read back the published port, and
poll the relay with the token until Edge answers.
"""

import os
import secrets
import socket
import subprocess
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from browser_tool.backends import IMAGE
from browser_tool.policy import BLOCKED_GUEST_CIDRS

SECCOMP_PATH = Path(__file__).resolve().parent.parent / "seccomp.json"
RELAY_PORT = 9333
READY_TIMEOUT_S = 30.0
READY_POLL_S = 0.5
HTTP_TIMEOUT_S = 3.0
DOCKER_TIMEOUT_S = 120.0
# docker.exe is a console program: without this flag a windowless parent (the MCP
# server) would flash a console window on every call.
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
# Never send relay traffic through a system proxy.
_DIRECT = urllib.request.build_opener(urllib.request.ProxyHandler({}))


@dataclass(frozen=True)
class Job:
    """One running browser container."""

    name: str
    port: int
    token: str

    @property
    def endpoint(self) -> str:
        """The relay's HTTP endpoint on the host's loopback."""
        return f"http://127.0.0.1:{self.port}"

    @property
    def auth_headers(self) -> dict[str, str]:
        """The header every relay connection must carry."""
        return {"Authorization": f"Bearer {self.token}"}


def docker(
    *args: str, env: dict[str, str] | None = None, stdin_text: str | None = None, check: bool = True
) -> subprocess.CompletedProcess[str]:
    """Run one docker CLI command without a console window and return its output.

    Raises:
        subprocess.CalledProcessError: If `check` and docker exits non-zero.
    """
    return subprocess.run(
        ["docker", *args],
        capture_output=True,
        text=True,
        env=env,
        input=stdin_text,
        check=check,
        timeout=DOCKER_TIMEOUT_S,
        creationflags=NO_WINDOW,
    )


def host_ipv4s() -> list[str]:
    """The host's IPv4 addresses, as the backend will compute them at each job start."""
    infos = socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET)
    return sorted({info[4][0] for info in infos})


def block_cidrs() -> str:
    """SIGNAL_BLOCK_CIDRS: the fixed private ranges plus each host address as a /32."""
    return ",".join([*BLOCKED_GUEST_CIDRS, *(f"{address}/32" for address in host_ipv4s())])


def job_environment(token: str, resolver_rules: str, block_list: str) -> dict[str, str]:
    """docker's own environment for `docker run`, holding the three SIGNAL_* values.

    `-e NAME` with no value copies NAME from here, so the token never appears
    on a command line.
    """
    return {
        **os.environ,
        "SIGNAL_RELAY_TOKEN": token,
        "SIGNAL_BLOCK_CIDRS": block_list,
        "SIGNAL_RESOLVER_RULES": resolver_rules,
    }


def run_arguments(name: str, job_id: str) -> list[str]:
    """Everything after `docker run` except -d: the design doc's run line (4.3)."""
    return [
        "--rm",
        "--init",
        "--name",
        name,
        "--label",
        f"signal.browser.job={job_id}",
        "--cap-drop=ALL",
        "--cap-add=NET_ADMIN",
        "--cap-add=SETUID",
        "--cap-add=SETGID",
        "--cap-add=SETPCAP",
        "--security-opt",
        "no-new-privileges",
        "--security-opt",
        f"seccomp={SECCOMP_PATH}",
        "--sysctl",
        "net.ipv6.conf.all.disable_ipv6=1",
        "-p",
        f"127.0.0.1::{RELAY_PORT}",
        "-e",
        "SIGNAL_RELAY_TOKEN",
        "-e",
        "SIGNAL_BLOCK_CIDRS",
        "-e",
        "SIGNAL_RESOLVER_RULES",
        IMAGE,
    ]


def start_job(job_id: str, resolver_rules: str = "") -> Job:
    """`docker run -d` one browser container and return it once its port is published.

    Args:
        job_id: Short id for the container name and label.
        resolver_rules: Passed to Edge as --host-resolver-rules.

    Raises:
        subprocess.CalledProcessError: If docker refuses to start it.
    """
    token = secrets.token_urlsafe(32)
    name = f"signal-browser-spike-{job_id}"
    env = job_environment(token, resolver_rules, block_cidrs())
    docker("run", "-d", *run_arguments(name, job_id), env=env)
    return Job(name=name, port=_published_port(name), token=token)


def relay_status(job: Job, headers: dict[str, str] | None) -> int | None:
    """GET /json/version through the relay. Returns the status, or None if the connection failed."""
    request = urllib.request.Request(f"{job.endpoint}/json/version", headers=headers or {})
    try:
        with _DIRECT.open(request, timeout=HTTP_TIMEOUT_S) as response:
            return response.status
    except urllib.error.HTTPError as error:
        return error.code
    except (OSError, urllib.error.URLError):
        return None


def wait_ready(job: Job) -> float:
    """Poll the relay with the token until it answers 200. Returns the seconds it took.

    A bare TCP connect isn't enough: Docker Desktop's port proxy accepts
    connections on the host before anything listens in the container.

    Raises:
        TimeoutError: "the browser container didn't start" after READY_TIMEOUT_S.
    """
    started = time.monotonic()
    while time.monotonic() - started < READY_TIMEOUT_S:
        if relay_status(job, job.auth_headers) == 200:
            return time.monotonic() - started
        time.sleep(READY_POLL_S)
    raise TimeoutError("the browser container didn't start")


def is_running(name: str) -> bool:
    """True while a container with this exact name exists."""
    names = docker("ps", "-a", "--filter", f"name=^{name}$", "--format", "{{.Names}}").stdout
    return name in names.split()


def remove_job_async(name: str) -> subprocess.Popen[bytes]:
    """Start `docker rm -f` and return without waiting (for synchronous close handlers)."""
    return subprocess.Popen(
        ["docker", "rm", "-f", name],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=NO_WINDOW,
    )


def _published_port(name: str) -> int:
    first_line = docker("port", name, f"{RELAY_PORT}/tcp").stdout.strip().splitlines()[0]
    host, _, port = first_line.rpartition(":")
    if host != "127.0.0.1":
        raise RuntimeError(f"relay published on {host}, expected 127.0.0.1")
    return int(port)
