"""Phase 0 checks on the relay and the container's exposure (security boundaries).

- Every unauthenticated, malformed or slow connection gets a 401 and is closed.
- The token opens /json/version, whose WebSocket URL points back at the published port.
- The relay is published on 127.0.0.1 only, nothing is mounted, nothing is privileged.
- Docker Desktop accepts a bare TCP connect with nothing listening, so the
  readiness poll must be an authenticated GET.
- After the host process is killed (taskkill /F), the container is gone within ~60 s.
"""

import json
import os
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import docker_job
from results import Result

RAW_TIMEOUT_S = 10.0
SLOW_CLIENT_MAX_S = 7.0
IDLE_EXIT_MAX_S = 75.0
POKE_INTERVAL_S = 10.0
GONE_POLL_S = 1.0
HOLDER_SCRIPT = Path(__file__).resolve().parent / "hold_browser.py"
HOLDER_READY_TIMEOUT_S = 60.0


def _rejection_cases(token: str) -> dict[str, bytes]:
    """Requests the relay must refuse, by name. b"" means connect and stay silent."""

    def get(*headers: str, method: str = "GET", path: str = "/json/version") -> bytes:
        return "\r\n".join(
            [f"{method} {path} HTTP/1.1", "Host: 127.0.0.1", *headers, "", ""]
        ).encode()

    return {
        "no token": get(),
        "wrong token": get("Authorization: Bearer " + "x" * len(token)),
        "Basic scheme": get(f"Authorization: Basic {token}"),
        "two Authorization headers": get(
            f"Authorization: Bearer {token}", "Authorization: Bearer x"
        ),
        "POST with token": get(f"Authorization: Bearer {token}", method="POST"),
        "websocket, no token": get(
            "Upgrade: websocket", "Connection: Upgrade", path="/devtools/browser/x"
        ),
        "binary garbage": b"\x16\x03\x01\x02\x00\x01\x00\x01\xfc\x03\x03\r\n\r\n",
        "oversized head": b"GET / HTTP/1.1\r\nX: " + b"a" * 20000,
        "silent client": b"",
    }


def check_rejections(job: docker_job.Job) -> Result:
    """Each rejection case gets a 401 (or a reset) and is closed; the silent one within ~5 s."""
    outcomes = {}
    for name, payload in _rejection_cases(job.token).items():
        reply, seconds = _raw_exchange(job.port, payload)
        refused = reply.startswith(b"HTTP/1.1 401") or reply == b"<reset>"
        in_time = seconds < SLOW_CLIENT_MAX_S
        outcomes[name] = (
            refused and in_time,
            reply[:12].decode(errors="replace"),
            round(seconds, 1),
        )
    passed = all(ok for ok, _, _ in outcomes.values())
    return Result("relay rejects bad connections", passed, f"{outcomes}")


def check_token_accepted(job: docker_job.Job) -> Result:
    """12 (relay side): the token opens /json/version, and the WebSocket URL uses our Host."""
    request = urllib.request.Request(f"{job.endpoint}/json/version", headers=job.auth_headers)
    with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(request) as response:
        body = json.loads(response.read())
    ws_url = body.get("webSocketDebuggerUrl", "")
    passed = ws_url.startswith(f"ws://127.0.0.1:{job.port}/devtools/browser/")
    return Result("relay accepts the token", passed, f"{body.get('Browser')}, ws {ws_url[:48]}...")


def check_relay_log(job: docker_job.Job) -> Result:
    """12 (Playwright side): connect_over_cdp sent the token on /json/version AND the WebSocket."""
    logs = docker_job.docker("logs", job.name).stderr
    accepted = [line.split("accepted ")[1] for line in logs.splitlines() if "accepted " in line]
    passed = any(a.startswith("GET /json/version") for a in accepted) and any(
        a.startswith("websocket /devtools/browser/") for a in accepted
    )
    return Result(
        "12 headers on both connections", passed, f"relay accepted {sorted(set(accepted))}"
    )


def check_exposure(job: docker_job.Job) -> Result:
    """Port bound to 127.0.0.1 only, no mounts, not privileged, only the four added caps."""
    inspected = json.loads(docker_job.docker("inspect", job.name).stdout)[0]
    host_config = inspected["HostConfig"]
    bindings = host_config["PortBindings"]
    host_ips = {binding["HostIp"] for port in bindings.values() for binding in port}
    facts = {
        "port host IPs": sorted(host_ips),
        "mounts": inspected["Mounts"],
        "privileged": host_config["Privileged"],
        "cap add": sorted(host_config["CapAdd"]),
        "cap drop": host_config["CapDrop"],
        "security opts": [opt.split("=")[0] for opt in host_config["SecurityOpt"]],
    }
    passed = (
        facts["port host IPs"] == ["127.0.0.1"]
        and not facts["mounts"]
        and not facts["privileged"]
        and facts["cap add"] == ["CAP_NET_ADMIN", "CAP_SETGID", "CAP_SETPCAP", "CAP_SETUID"]
    )
    return Result("port exposure and mounts", passed, f"{facts}")


def check_bare_connect_without_listener() -> Result:
    """Why readiness is an authenticated GET: is a TCP connect accepted with nothing listening?"""
    name = "signal-browser-spike-nolistener"
    docker_job.docker(
        "run",
        "-d",
        "--rm",
        "--name",
        name,
        "--cap-drop=ALL",
        "-p",
        f"127.0.0.1::{docker_job.RELAY_PORT}",
        "--entrypoint",
        "sleep",
        docker_job.IMAGE,
        "60",
    )
    try:
        port = int(
            docker_job.docker("port", name, f"{docker_job.RELAY_PORT}/tcp").stdout.split(":")[-1]
        )
        reply, seconds = _raw_exchange(port, b"GET / HTTP/1.1\r\nHost: x\r\n\r\n")
        accepted = reply != b"<refused>"
    finally:
        docker_job.docker("rm", "-f", name, check=False)
    detail = f"bare connect accepted: {accepted}, then got {reply[:20]!r} after {seconds:.1f} s"
    return Result("readiness needs an authenticated GET", True, detail)


def check_idle_exit_after_kill() -> Result:
    """Kill a connected host process (like taskkill /F); the container must be gone in ~60 s.

    Unauthenticated pokes keep arriving meanwhile, and must not keep it alive.
    """
    job = docker_job.start_job("kill")
    try:
        docker_job.wait_ready(job)
        holder = subprocess.Popen(
            [sys.executable, "-I", str(HOLDER_SCRIPT), str(job.port)],
            stdout=subprocess.PIPE,
            text=True,
            creationflags=docker_job.NO_WINDOW,
            env={**os.environ, "SIGNAL_RELAY_TOKEN": job.token},
        )
        connected = holder.stdout.readline().strip() == "connected"
        holder.kill()
        killed_at = last_poke = time.monotonic()
        while docker_job.is_running(job.name) and time.monotonic() - killed_at < IDLE_EXIT_MAX_S:
            if time.monotonic() - last_poke >= POKE_INTERVAL_S:
                _raw_exchange(job.port, b"GET / HTTP/1.1\r\n\r\n")
                last_poke = time.monotonic()
            time.sleep(GONE_POLL_S)
        gone_after = time.monotonic() - killed_at
        gone = not docker_job.is_running(job.name)
    finally:
        docker_job.docker("rm", "-f", job.name, check=False)
    passed = connected and gone
    return Result(
        "container gone after taskkill /F",
        passed,
        f"holder connected {connected}, gone after {gone_after:.0f} s",
    )


def _raw_exchange(port: int, payload: bytes) -> tuple[bytes, float]:
    """Send `payload`, read until the relay closes. Returns (reply, seconds until closed)."""
    started = time.monotonic()
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=RAW_TIMEOUT_S) as connection:
            if payload:
                connection.sendall(payload)
            chunks = []
            while chunk := connection.recv(65536):
                chunks.append(chunk)
            return b"".join(chunks), time.monotonic() - started
    except ConnectionRefusedError:
        return b"<refused>", time.monotonic() - started
    except ConnectionResetError:
        return b"<reset>", time.monotonic() - started
    except TimeoutError:
        return b"<timeout>", time.monotonic() - started
