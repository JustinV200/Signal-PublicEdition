"""ensure_daemon: make sure the sessions daemon is running, starting it in the background if not.

The CLI and the MCP server call this before talking to the daemon. A started
daemon is independent of its starter: it runs in its own process group and
survives the MCP server (and the Claude Code window) closing.

Process flags: CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP, not DETACHED_PROCESS.
A detached daemon has no console, so Windows gives every console program it
starts (each session's claude.exe) a new *visible* console window. With
CREATE_NO_WINDOW the daemon owns a hidden console that its children share.
CREATE_BREAKAWAY_FROM_JOB is tried first so the daemon leaves the starter's job
object (which may kill the whole tree when the starter exits); jobs that
forbid breakaway refuse it, and then the daemon starts without it.
"""

import asyncio
import logging
import subprocess
import sys
import time
from collections.abc import Callable
from typing import Any

from claude_sessions.config import TOOL_ROOT, Settings, daemon_log_file, daemon_token_file
from claude_sessions.ipc.client import (
    DaemonEndpoint,
    DaemonNotRunningError,
    DaemonRequestError,
    call_daemon,
)
from claude_sessions.ipc.protocol import ProtocolError
from claude_sessions.tokens import read_token

logger = logging.getLogger(__name__)

CREATE_NEW_PROCESS_GROUP = 0x00000200
CREATE_BREAKAWAY_FROM_JOB = 0x01000000
CREATE_NO_WINDOW = 0x08000000
DAEMON_FLAGS = CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP

STARTUP_TIMEOUT_S = 20.0
POLL_INTERVAL_S = 0.25

SpawnDaemon = Callable[[Settings], None]


class DaemonStartError(RuntimeError):
    """The daemon was started but never answered, or something else answers on its port."""


async def ensure_daemon(settings: Settings, spawn: SpawnDaemon | None = None) -> None:
    """Return once the daemon answers ping, starting it first if needed.

    Args:
        settings: The daemon's address and state folder.
        spawn: Starts the daemon process; tests pass a fake. Default spawn_daemon.

    Raises:
        DaemonStartError: The daemon didn't answer within STARTUP_TIMEOUT_S, or
            the port answers but refuses our token (see is_daemon_running).
        OSError: The daemon process couldn't be started.
    """
    if await is_daemon_running(settings):
        return
    logger.info("Starting the sessions daemon on port %d", settings.daemon_port)
    (spawn or spawn_daemon)(settings)
    deadline = time.monotonic() + STARTUP_TIMEOUT_S
    while time.monotonic() < deadline:
        await asyncio.sleep(POLL_INTERVAL_S)
        if await is_daemon_running(settings):
            return
    log_path = daemon_log_file(settings.state_dir)
    raise DaemonStartError(
        f"the sessions daemon didn't start within {STARTUP_TIMEOUT_S:.0f} s; see {log_path}"
    )


async def call_running_daemon(
    settings: Settings, op: str, args: dict[str, Any] | None = None
) -> Any:
    """Send one request, starting the daemon first if nothing answers (what the CLI and MCP use).

    The daemon is nearly always up, so the request goes straight out; only a
    missing token file or a refused connection starts the daemon and retries once.

    Args:
        settings: The daemon's address and state folder.
        op: The operation, e.g. "start".
        args: Its arguments.

    Returns:
        The daemon's result.

    Raises:
        DaemonStartError, OSError: See ensure_daemon.
        ProtocolError, PermissionModeError, DaemonRequestError, TimeoutError: See call_daemon.
    """
    endpoint = daemon_endpoint(settings)
    if endpoint is not None:
        try:
            return await call_daemon(endpoint, op, args)
        except DaemonNotRunningError:
            logger.info("The sessions daemon isn't answering; starting it")
    await ensure_daemon(settings)
    endpoint = daemon_endpoint(settings)
    if endpoint is None:
        raise DaemonNotRunningError("the sessions daemon's token file is missing")
    return await call_daemon(endpoint, op, args)


def daemon_endpoint(settings: Settings) -> DaemonEndpoint | None:
    """The daemon's address with the token from its token file.

    Args:
        settings: The daemon's address and state folder.

    Returns:
        The endpoint, or None when there is no token file (no daemon has started).
    """
    token = read_token(daemon_token_file(settings.state_dir, settings.daemon_port))
    if token is None:
        return None
    return DaemonEndpoint(settings.daemon_host, settings.daemon_port, token)


async def is_daemon_running(settings: Settings) -> bool:
    """Say whether the daemon answers ping.

    The token file is read afresh each time: a daemon that just started has
    written a new token before it begins listening.

    Args:
        settings: The daemon's address and state folder.

    Returns:
        True when it replied, False when there is no token or nothing is listening.

    Raises:
        DaemonStartError: Something answers on the port but not as our daemon
            (a stale token, another program, or a hung daemon). Starting a
            second daemon there could never bind, so this fails at once instead.
    """
    endpoint = daemon_endpoint(settings)
    if endpoint is None:
        return False
    try:
        await call_daemon(endpoint, "ping")
    except DaemonNotRunningError:
        return False
    except (DaemonRequestError, ProtocolError, TimeoutError) as error:
        raise DaemonStartError(
            f"something answers on port {settings.daemon_port} but not as the sessions daemon "
            f"with the token in {daemon_token_file(settings.state_dir, settings.daemon_port)} "
            f"({error}); a stale token or another program holds the port. Stop it, or restart "
            "the daemon (or its process) by hand."
        ) from error
    return True


def spawn_daemon(settings: Settings) -> None:
    """Start `python -m claude_sessions serve` in the background, logging to the state folder.

    Args:
        settings: Supplies the port and state folder. Other settings come from
            the inherited environment, as for any other run.

    Raises:
        OSError: The process couldn't be started.
    """
    log_path = daemon_log_file(settings.state_dir)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    command = [
        sys.executable,
        "-m",
        "claude_sessions",
        "serve",
        "--port",
        str(settings.daemon_port),
    ]
    with log_path.open("ab") as log_file:
        try:
            _popen(command, log_file, DAEMON_FLAGS | CREATE_BREAKAWAY_FROM_JOB)
        except PermissionError:
            # The starter's job object doesn't allow breakaway; stay in it.
            logger.info("Job object refused breakaway; starting the daemon inside it")
            _popen(command, log_file, DAEMON_FLAGS)
    logger.info("Sessions daemon starting; log at %s", log_path)


def _popen(command: list[str], log_file: object, creation_flags: int) -> None:
    """Start the daemon process with its output appended to log_file."""
    # A fixed command: our own interpreter running our own module.
    subprocess.Popen(
        command,
        cwd=TOOL_ROOT,
        stdin=subprocess.DEVNULL,
        stdout=log_file,
        stderr=subprocess.STDOUT,
        creationflags=creation_flags,
        close_fds=True,
    )
