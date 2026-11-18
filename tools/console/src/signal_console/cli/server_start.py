"""`console open`'s server start: check the port, start `serve` detached, wait for its login key.

Each step says what happens, so a failure is reported in words at once rather
than after the whole wait: a port another program holds (the health package's
port row, which only reads the socket table and never connects, so no key or
token reaches that program), and a server that exits during the wait (the last
line of its server.log, which is where its output goes).
"""

import os
import subprocess
import sys
import time
from pathlib import Path

from signal_console.health import OK, HealthPaths, port_row
from signal_console.launch import clean_env, spawn_detached
from signal_console.local_api import LOGIN_KEY_PATH, ConsoleNotRunningError, post_local
from signal_console.open_hint import open_command
from signal_console.paths import SERVER_LOG_FILE, TOOL_ROOT
from signal_console.state_files import ensure_state_dir

REQUEST_TIMEOUT_S = 2.0
STARTUP_TIMEOUT_S = 15.0
POLL_INTERVAL_S = 0.25
# Only the end of server.log is read: the failed start's reason is its last line.
LOG_TAIL_BYTES = 8 * 1024
# asyncio's message for a port it can't take ("error while attempting to bind on address").
BIND_ERROR_WORD = "bind"


class OpenError(RuntimeError):
    """The server didn't come up, or Edge couldn't be started."""


def login_key(state_dir: Path) -> str | None:
    """A one-time login key from this checkout's running server, or None when none runs.

    post_local sends the local key only to the server daemon.json names, and only
    while that process runs.

    Raises:
        OpenError: The server answered without a key.
    """
    try:
        reply = post_local(state_dir, LOGIN_KEY_PATH, {}, REQUEST_TIMEOUT_S)
    except ConsoleNotRunningError:
        return None
    key = reply.get("key")
    if not isinstance(key, str):
        raise OpenError("the console server gave no login key")
    return key


def start_server(paths: HealthPaths) -> str:
    """Start this checkout's server on `paths.default_port` and return its first login key.

    Raises:
        OpenError: Another program holds the port, the server exited during the wait
            (with the last line of its log), or it didn't answer in time.
        OSError: The server couldn't be started.
    """
    port_check = port_row(paths)
    if port_check.level != OK:
        fix = f"{port_check.fix} {port_check.command or ''}".strip()
        raise OpenError(f"{port_check.words} {fix}")
    print("Starting the console server...")
    ensure_state_dir(paths.state_dir)
    command = [sys.executable, "-m", "signal_console", "serve", "--port", str(paths.default_port)]
    # Output goes to server.log, which also catches a crash before logging starts; serve
    # sees its stderr is that file and adds no second writer (cli/server_log.py).
    with (paths.state_dir / SERVER_LOG_FILE).open("ab") as log_file:
        process = spawn_detached(command, TOOL_ROOT, log_file, clean_env(os.environ))
    return _wait_for_login_key(paths, process)


def _wait_for_login_key(paths: HealthPaths, process: subprocess.Popen[bytes]) -> str:
    # Poll for the key; a server that exits meanwhile won't answer, so say why now.
    deadline = time.monotonic() + STARTUP_TIMEOUT_S
    while time.monotonic() < deadline:
        time.sleep(POLL_INTERVAL_S)
        key = login_key(paths.state_dir)
        if key is not None:
            return key
        if process.poll() is not None:
            raise OpenError(_exit_words(paths, process.returncode))
    raise OpenError(
        f"the console server didn't start within {STARTUP_TIMEOUT_S:.0f} s; "
        f"see {paths.state_dir / SERVER_LOG_FILE}"
    )


def _exit_words(paths: HealthPaths, exit_code: int) -> str:
    # The server's reason, and the --port way out when it couldn't take the port.
    log_path = paths.state_dir / SERVER_LOG_FILE
    words = f"the console server stopped at once (exit {exit_code})"
    last = _last_line(log_path)
    if last:
        words += f". The last line of {log_path}: {last}"
    if BIND_ERROR_WORD in last.casefold():
        words += (
            f". Another program may hold port {paths.default_port}: stop it, or run "
            f"{open_command(paths.tool_root)} --port <a free port>"
        )
    return words


def _last_line(log_path: Path) -> str:
    # The last non-empty line of the log's tail, or "" when there's no log to read.
    try:
        with log_path.open("rb") as log_file:
            size = log_file.seek(0, os.SEEK_END)
            log_file.seek(max(0, size - LOG_TAIL_BYTES))
            tail = log_file.read().decode("utf-8", errors="replace")
    except OSError:
        return ""
    lines = [line.strip() for line in tail.splitlines() if line.strip()]
    return lines[-1] if lines else ""
