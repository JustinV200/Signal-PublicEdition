"""Start and stop the browser container's child processes: Xvfb and Edge.

Part of the docker backend's guest (refdocs/research/docker-browser.md section 3). main.py
calls these as user "edge". Both children get an explicit, minimal environment,
so the relay token (and anything else in the relay's own environment) never
reaches them.
"""

import asyncio
import logging
import os
import urllib.request
from asyncio.subprocess import DEVNULL, Process
from collections.abc import Callable

from edge_switches import EDGE_SWITCHES

logger = logging.getLogger(__name__)

DISPLAY = ":99"
# Matches a common desktop size, so pages lay out as they would on the host.
SCREEN = "1920x1080x24"
X_SOCKET = "/tmp/.X11-unix/X99"
EDGE_HOME = "/home/edge"
# Chromium 136+ ignores --remote-debugging-port with the default profile dir.
PROFILE_DIR = "/home/edge/profile"
CDP_PORT = 9222
CDP_VERSION_URL = f"http://127.0.0.1:{CDP_PORT}/json/version"
# Edge's launcher is a shell script, so it needs a PATH to find its tools.
CHILD_PATH = "/usr/local/bin:/usr/bin:/bin"
START_TIMEOUT_S = 30.0
POLL_INTERVAL_S = 0.25
CDP_PROBE_TIMEOUT_S = 1.0
STOP_GRACE_S = 5.0


def child_env() -> dict[str, str]:
    """The whole environment Xvfb and Edge get: no SIGNAL_* variables."""
    return {"DISPLAY": DISPLAY, "HOME": EDGE_HOME, "PATH": CHILD_PATH}


def edge_command(resolver_rules: str) -> list[str]:
    """Edge's argv. `resolver_rules` is passed as one element, never through a shell."""
    command = [
        "microsoft-edge",
        *EDGE_SWITCHES,
        f"--remote-debugging-port={CDP_PORT}",
        f"--user-data-dir={PROFILE_DIR}",
    ]
    if resolver_rules:
        command.append(f"--host-resolver-rules={resolver_rules}")
    return [*command, "about:blank"]


async def start_xvfb() -> Process:
    """Start Xvfb with TCP listening off and wait for its socket.

    Raises:
        RuntimeError: If Xvfb exits before it is ready.
        TimeoutError: If it isn't ready within START_TIMEOUT_S.
    """
    xvfb = await asyncio.create_subprocess_exec(
        "Xvfb",
        DISPLAY,
        "-nolisten",
        "tcp",
        "-screen",
        "0",
        SCREEN,
        env=child_env(),
        stdin=DEVNULL,
    )
    await _wait_until(lambda: os.path.exists(X_SOCKET), xvfb, "Xvfb")
    return xvfb


async def start_edge(resolver_rules: str) -> Process:
    """Start Edge on the Xvfb display and wait until its CDP port answers.

    Edge's stderr goes to the container log, so sandbox errors show in `docker logs`.

    Raises:
        RuntimeError: If Edge exits before CDP answers.
        TimeoutError: If CDP doesn't answer within START_TIMEOUT_S.
    """
    edge = await asyncio.create_subprocess_exec(
        *edge_command(resolver_rules), env=child_env(), stdin=DEVNULL
    )
    await _wait_until(_cdp_answers, edge, "Edge")
    return edge


async def stop_all(processes: list[Process | None]) -> None:
    """Terminate each running process, killing any that outlast STOP_GRACE_S."""
    for process in processes:
        if process is None or process.returncode is not None:
            continue
        process.terminate()
        try:
            await asyncio.wait_for(process.wait(), STOP_GRACE_S)
        except TimeoutError:
            process.kill()
            await process.wait()


def _cdp_answers() -> bool:
    try:
        with urllib.request.urlopen(CDP_VERSION_URL, timeout=CDP_PROBE_TIMEOUT_S) as response:
            return response.status == 200
    except OSError:
        # Not listening yet (connection refused or reset); keep polling.
        return False


async def _wait_until(is_ready: Callable[[], bool], process: Process, name: str) -> None:
    loop = asyncio.get_running_loop()
    deadline = loop.time() + START_TIMEOUT_S
    while not await asyncio.to_thread(is_ready):
        if process.returncode is not None:
            raise RuntimeError(f"{name} exited with status {process.returncode}")
        if loop.time() > deadline:
            raise TimeoutError(f"{name} wasn't ready after {START_TIMEOUT_S} s")
        await asyncio.sleep(POLL_INTERVAL_S)
    logger.info("%s is ready", name)
