"""Drive the docker CLI for browser jobs: check Docker, run, wait for, and remove a container.

No Python dependency: every call is `docker ...` through subprocess, with
CREATE_NO_WINDOW, because docker.exe is a console program and the MCP server
has no console, so each call would otherwise flash a window. The calls block,
so the backend runs them in a worker thread. The run line follows
refdocs/research/docker-browser.md section 3. The relay token reaches the container
through docker's own environment (`-e NAME` with no value), never a command line.
"""

import http.client
import logging
import os
import subprocess
import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from browser_tool.backends.types import BackendError

logger = logging.getLogger(__name__)

# Read with getattr so the module imports off Windows too.
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
DOCKER_TIMEOUT_S = 120.0
INFO_TIMEOUT_S = 20.0
RELAY_PORT = 9333
CONTAINER_PREFIX = "signal-browser-"
JOB_LABEL_KEY = "signal.browser.job"
ENV_TOKEN = "SIGNAL_RELAY_TOKEN"
ENV_BLOCK_CIDRS = "SIGNAL_BLOCK_CIDRS"
ENV_RESOLVER_RULES = "SIGNAL_RESOLVER_RULES"
LOOPBACK = "127.0.0.1"
READY_TIMEOUT_S = 30.0
READY_POLL_S = 0.5
READY_REQUEST_TIMEOUT_S = 3.0
HTTP_OK = 200
DID_NOT_START = "the browser container didn't start"
DOCKER_NOT_RUNNING = "Docker Desktop isn't running. Start it and try again."
DOCKER_NO_ANSWER = "docker didn't answer; check that Docker Desktop is running"
# Never send relay traffic through a system proxy.
_DIRECT = urllib.request.build_opener(urllib.request.ProxyHandler({}))
# `docker rm -f` processes still running, kept so they aren't collected mid-run.
_removals: set[subprocess.Popen[bytes]] = set()


@dataclass(frozen=True)
class JobSpec:
    """What one job's container is started with."""

    job_id: str
    token: str
    block_cidrs: str
    resolver_rules: str


@dataclass(frozen=True)
class Job:
    """One running browser container, reachable on the host's loopback."""

    job_id: str
    name: str
    port: int
    token: str

    @property
    def endpoint(self) -> str:
        """The relay's address on the host."""
        return f"http://{LOOPBACK}:{self.port}"

    @property
    def auth_headers(self) -> dict[str, str]:
        """The header every connection to the relay must carry."""
        return {"Authorization": f"Bearer {self.token}"}


def run_docker(
    *args: str, env: dict[str, str] | None = None, timeout_s: float = DOCKER_TIMEOUT_S
) -> subprocess.CompletedProcess[str]:
    """Run `docker <args>` without a console window. A non-zero exit is returned, not raised.

    Raises:
        BackendError: DOCKER_NO_ANSWER if docker can't be run (e.g. not
            installed) or outlasts `timeout_s`.
    """
    try:
        return subprocess.run(
            ["docker", *args],
            capture_output=True,
            text=True,
            env=env,
            timeout=timeout_s,
            check=False,
            creationflags=NO_WINDOW,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        logger.warning("docker %s failed: %s", args[0] if args else "", type(error).__name__)
        raise BackendError(DOCKER_NO_ANSWER) from None


def ensure_docker_running() -> None:
    """Check that the Docker engine answers `docker info` (the lazy start check).

    Raises:
        BackendError: DOCKER_NOT_RUNNING if it doesn't.
    """
    try:
        result = run_docker("info", "--format", "{{.ServerVersion}}", timeout_s=INFO_TIMEOUT_S)
    except BackendError:
        raise BackendError(DOCKER_NOT_RUNNING) from None
    if result.returncode != 0:
        raise BackendError(DOCKER_NOT_RUNNING)


def image_id(image: str) -> str | None:
    """The local image's id, or None if it isn't built.

    Raises:
        BackendError: If docker doesn't answer.
    """
    result = run_docker("image", "inspect", "--format", "{{.Id}}", image)
    if result.returncode != 0:
        return None
    return result.stdout.strip() or None


def image_edge_version(image: str) -> str:
    """`microsoft-edge --version` inside `image`, run with no network.

    Raises:
        BackendError: If docker doesn't answer or the image can't report it.
    """
    result = run_docker(
        "run", "--rm", "--network", "none", "--entrypoint", "microsoft-edge", image, "--version"
    )
    if result.returncode != 0:
        raise BackendError(f"couldn't read the Edge version in {image}")
    return result.stdout.strip()


def run_arguments(spec: JobSpec, image: str, seccomp_path: Path) -> list[str]:
    """Everything after `docker run -d`: the design's run line.

    Published on the host's loopback only, with no mounts, all capabilities
    dropped but the four the entrypoint needs, and the profile that lets
    Chromium's namespace sandbox start.
    """
    return [
        "--rm",
        "--init",
        "--name",
        CONTAINER_PREFIX + spec.job_id,
        "--label",
        f"{JOB_LABEL_KEY}={spec.job_id}",
        "--cap-drop=ALL",
        "--cap-add=NET_ADMIN",
        "--cap-add=SETUID",
        "--cap-add=SETGID",
        "--cap-add=SETPCAP",
        "--security-opt",
        "no-new-privileges",
        "--security-opt",
        f"seccomp={seccomp_path}",
        "--sysctl",
        "net.ipv6.conf.all.disable_ipv6=1",
        "-p",
        f"{LOOPBACK}::{RELAY_PORT}",
        *("-e", ENV_TOKEN, "-e", ENV_BLOCK_CIDRS, "-e", ENV_RESOLVER_RULES),
        image,
    ]


def job_environment(spec: JobSpec) -> dict[str, str]:
    """docker's own environment for `docker run`: this process's plus the three SIGNAL_* values."""
    return {
        **os.environ,
        ENV_TOKEN: spec.token,
        ENV_BLOCK_CIDRS: spec.block_cidrs,
        ENV_RESOLVER_RULES: spec.resolver_rules,
    }


def start_job(spec: JobSpec, image: str, seccomp_path: Path) -> Job:
    """`docker run -d` one browser container and read back its published port.

    Raises:
        BackendError: If docker doesn't answer or refuses to start it, or the port
            isn't on loopback.
    """
    name = CONTAINER_PREFIX + spec.job_id
    arguments = run_arguments(spec, image, seccomp_path)
    result = run_docker("run", "-d", *arguments, env=job_environment(spec))
    if result.returncode != 0:
        logger.error("docker run failed: %s", _last_line(result.stderr))
        raise BackendError(DID_NOT_START)
    try:
        return Job(spec.job_id, name, _published_port(name), spec.token)
    except BackendError:
        remove_job_async(name)
        raise


def wait_ready(job: Job) -> None:
    """Poll the relay with the token until /json/version answers 200.

    A bare TCP connect isn't readiness: Docker Desktop's port proxy accepts a
    connection with nothing listening in the container, then closes it.

    Raises:
        BackendError: DID_NOT_START after READY_TIMEOUT_S.
    """
    deadline = time.monotonic() + READY_TIMEOUT_S
    request = urllib.request.Request(f"{job.endpoint}/json/version", headers=job.auth_headers)
    while time.monotonic() < deadline:
        try:
            with _DIRECT.open(request, timeout=READY_REQUEST_TIMEOUT_S) as response:
                if response.status == HTTP_OK:
                    return
        except (OSError, http.client.HTTPException):
            # Not listening yet (refused, reset, a bad reply or an HTTP error): keep polling.
            pass
        time.sleep(READY_POLL_S)
    raise BackendError(DID_NOT_START)


def remove_job_async(name: str) -> None:
    """Start `docker rm -f <name>` and return at once (close handlers can't wait)."""
    for finished in [process for process in _removals if process.poll() is not None]:
        _removals.discard(finished)
    try:
        process = subprocess.Popen(
            ["docker", "rm", "-f", name],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=NO_WINDOW,
        )
    except OSError as error:
        # The relay's idle exit still ends the container within about a minute.
        logger.error("couldn't start docker rm for %s: %s", name, type(error).__name__)
        return
    _removals.add(process)


def _published_port(name: str) -> int:
    lines = run_docker("port", name, f"{RELAY_PORT}/tcp").stdout.strip().splitlines()
    host, _, port = lines[0].rpartition(":") if lines else ("", "", "")
    if host != LOOPBACK or not port.isdigit():
        logger.error("relay of %s published on %r, expected %s", name, host, LOOPBACK)
        raise BackendError(DID_NOT_START)
    return int(port)


def _last_line(text: str) -> str:
    lines = text.strip().splitlines()
    return lines[-1] if lines else ""
