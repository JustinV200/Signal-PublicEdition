"""DaemonConnection: finds the running daemon, or starts it detached and waits until it's ready.

The MCP server and CLI go through this, so the first board_* call (not
merely starting `whiteboard mcp`) brings the daemon, camera and projector
kiosk up. Starting it lazily keeps every Claude session in the repo from
lighting the projector just by loading .mcp.json.
"""

import logging
import subprocess
import sys
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, TypeVar

from whiteboard.daemon_client.http_api import (
    DaemonApi,
    DaemonApiError,
    DaemonAuthError,
    DaemonUnreachableError,
)
from whiteboard.daemon_client.state_files import LOG_FILE, read_daemon_info, read_token

logger = logging.getLogger(__name__)

LOOPBACK_HOST = "127.0.0.1"
# Camera open plus Edge launch can take a while on a cold start.
READY_TIMEOUT_S = 45.0
POLL_INTERVAL_S = 0.5
# No console, and not killed by Ctrl+C in the terminal that started it.
DETACHED_FLAGS = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
# Also leave the caller's job object: `uv run` and Claude sessions kill their whole
# job on exit, which took a daemon started by a board_* call down with no log line.
BREAKAWAY_FLAGS = DETACHED_FLAGS | subprocess.CREATE_BREAKAWAY_FROM_JOB
# daemon.log is moved to daemon.log.1 past this size when a new daemon starts.
LOG_ROTATE_BYTES = 5 * 1024 * 1024

Result = TypeVar("Result")


class DaemonStartError(RuntimeError):
    """The daemon couldn't be started or didn't become ready in time."""


@dataclass(frozen=True)
class DaemonLocation:
    """Where to look for the daemon and how to start it.

    Attributes:
        state_dir: The .state/ folder holding daemon.json, token and the log.
        port: The configured port, used when daemon.json is missing.
        config_path: The --config file to pass to a daemon we start, if any.
    """

    state_dir: Path
    port: int
    config_path: Path | None = None


class DaemonConnection:
    """Thread-safe access to the daemon for the MCP server and CLI."""

    def __init__(self, location: DaemonLocation, is_auto_start: bool = True) -> None:
        """Create the connection. Nothing is contacted until call().

        Args:
            location: Where the daemon's files are and how to start it.
            is_auto_start: Start the daemon when none is running.
        """
        self._location = location
        self._is_auto_start = is_auto_start
        self._api: DaemonApi | None = None
        self._lock = threading.Lock()

    def call(self, operation: Callable[[DaemonApi], Result]) -> Result:
        """Run one API operation, connecting (or starting the daemon) first if needed.

        If the daemon went away since the last call, it's found or started again
        and the operation is retried once (it never reached a daemon, so that's safe).
        A 403 means our cached token or port is stale (the daemon restarted): the
        state files are re-read and, only if they changed, the operation is retried
        once (the daemon rejected it without acting, so that's safe too).

        Raises:
            DaemonStartError: No daemon and it couldn't be started.
            DaemonApiError: The daemon returned an error.
        """
        api = self._get_api(reuse=True)
        try:
            return operation(api)
        except DaemonUnreachableError:
            logger.info("Lost the whiteboard daemon; reconnecting")
            return operation(self._get_api(reuse=False))
        except DaemonAuthError as error:
            return operation(self._refresh_api(api, error))

    def _refresh_api(self, failed: DaemonApi, rejection: DaemonAuthError) -> DaemonApi:
        """Re-read daemon.json and the token after `failed` got a 403.

        Args:
            failed: The client whose request was rejected.
            rejection: Its 403, quoted if the retry can't help.

        Returns:
            A client for the current daemon, if it differs from `failed`.

        Raises:
            DaemonAuthError: The token and port are unchanged, or the daemon is gone.
        """
        with self._lock:
            # Another thread already refreshed while we waited for the lock.
            if self._api is not None and self._api is not failed:
                return self._api
            try:
                fresh = find_daemon(self._location)
            except DaemonAuthError:
                # find_daemon can't read the new token; treat it as unchanged so
                # the has_same_target check below raises with the 403 detail.
                fresh = failed
            if fresh is None:
                raise DaemonAuthError("couldn't reach the daemon after its token was rejected")
            if fresh.has_same_target(failed):
                raise DaemonAuthError(
                    f"daemon rejected the token after re-reading .state/token: {rejection}"
                )
            self._api = fresh
            return fresh

    def _get_api(self, reuse: bool) -> DaemonApi:
        """Return a client for a live daemon, starting one if allowed."""
        with self._lock:
            if reuse and self._api is not None:
                return self._api
            self._api = find_daemon(self._location) or self._start()
            return self._api

    def _start(self) -> DaemonApi:
        """Start the daemon detached and wait for it to answer."""
        if not self._is_auto_start:
            raise DaemonStartError("The whiteboard daemon isn't running. Start: whiteboard serve")
        process = spawn_daemon(self._location)
        return wait_until_ready(self._location, process)


def find_daemon(location: DaemonLocation) -> DaemonApi | None:
    """Return a client for the daemon if one answers /api/status, else None.

    Raises:
        DaemonApiError: Something answered but rejected us (e.g. a stale token).
    """
    token = read_token(location.state_dir)
    if token is None:
        return None
    info = read_daemon_info(location.state_dir)
    port = info.port if info is not None else location.port
    api = DaemonApi(f"http://{LOOPBACK_HOST}:{port}", token)
    try:
        api.status()
    except DaemonUnreachableError:
        return None
    return api


def spawn_daemon(location: DaemonLocation) -> subprocess.Popen[bytes]:
    """Start `whiteboard serve` as a detached process logging to .state/daemon.log.

    Returns:
        The process handle (used only to notice an early exit).
    """
    location.state_dir.mkdir(parents=True, exist_ok=True)
    command = [sys.executable, "-m", "whiteboard.cli", "serve"]
    if location.config_path is not None:
        command += ["--config", str(location.config_path)]
    log_path = location.state_dir / LOG_FILE
    _rotate_log(log_path)
    logger.info("Starting the whiteboard daemon (log: %s)", log_path)
    with open(log_path, "ab") as log:
        try:
            return _popen(command, log, BREAKAWAY_FLAGS)
        except PermissionError:
            # The caller's job forbids breakaway: start it inside the job, as before.
            logger.warning("Can't start the daemon outside this job; it ends with this session")
            return _popen(command, log, DETACHED_FLAGS)


def _popen(command: list[str], log: BinaryIO, flags: int) -> subprocess.Popen[bytes]:
    """Start `command` with no stdin, output to `log`, and the given creation flags."""
    return subprocess.Popen(
        command,
        stdin=subprocess.DEVNULL,
        stdout=log,
        stderr=subprocess.STDOUT,
        creationflags=flags,
        close_fds=True,
    )


def _rotate_log(log_path: Path) -> None:
    """Move a log past LOG_ROTATE_BYTES to <name>.1, replacing the previous one.

    Runs only when no daemon is up, so nothing holds the file open. A failure
    is logged and the old log just keeps growing.
    """
    try:
        if log_path.stat().st_size > LOG_ROTATE_BYTES:
            log_path.replace(log_path.with_name(log_path.name + ".1"))
    except FileNotFoundError:
        return
    except OSError as error:
        logger.warning("Couldn't rotate %s: %s", log_path, error)


def wait_until_ready(location: DaemonLocation, process: subprocess.Popen[bytes]) -> DaemonApi:
    """Poll until the new daemon answers, it exits, or READY_TIMEOUT_S passes.

    Raises:
        DaemonStartError: It exited early or never answered.
    """
    log_path = location.state_dir / LOG_FILE
    deadline = time.monotonic() + READY_TIMEOUT_S
    while time.monotonic() < deadline:
        try:
            api = find_daemon(location)
        except DaemonApiError:
            # The new daemon may not have replaced an old token file yet.
            api = None
        if api is not None:
            return api
        if process.poll() is not None:
            raise DaemonStartError(f"The whiteboard daemon exited at startup; see {log_path}")
        time.sleep(POLL_INTERVAL_S)
    raise DaemonStartError(
        f"The whiteboard daemon didn't answer within {READY_TIMEOUT_S:g} s; see {log_path}"
    )
