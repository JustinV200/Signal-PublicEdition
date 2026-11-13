"""Start, find and stop the voice hub: the one `console hub start` launched, or any other.

The hub runs detached (it outlives the session that asked for it) with its
output in .state/hub.log, which the server reads for the phase and the voice
feed. .state/hub.json keeps its pid and start time, so a reused pid is never
mistaken for it. Every hub also writes its own record (audiohub's
`.cache/hub.json`), which Stop falls back to for a hub started elsewhere.
Stop first asks the hub to shut down cleanly over its IPC (shutdown.py), so it
restores the music and closes its audio; only if it hasn't exited after a
short wait does it kill the hub's own processes (see _kill_tree), leaving
everything else the hub started.
"""

import asyncio
import contextlib
import os
import shutil
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import psutil

from signal_console.hub.shutdown import (
    GRACEFUL_EXIT_TIMEOUT_S,
    request_hub_shutdown,
    wait_for_exit,
)
from signal_console.launch import clean_env, spawn_detached
from signal_console.paths import (
    AUDIOHUB_ROOT,
    HUB_FILE,
    HUB_LOG_FILE,
    HUB_PREV_LOG_FILE,
    HUB_SELF_RECORD_PATH,
    REPO_ROOT,
)
from signal_console.process_record import find_recorded_process
from signal_console.process_tree import kill_processes, owned_tree
from signal_console.state_files import ensure_state_dir, read_json, write_json
from signal_console.status import is_hub_listening

# Run from the repo root; the hub reads its secrets from the repo's .env.
HUB_ARGS = [
    "run",
    "--env-file",
    ".env",
    "--project",
    "tools/audiohub",
    "--frozen",
    "--no-sync",
    "audiohub",
    "run",
]
# The status lines contain whatever Claude says, so never let a narrow code page mangle them.
HUB_ENCODING_ENV = {"PYTHONIOENCODING": "utf-8"}
# How long a start waits for the hub to listen (the STT model and Claude load first).
READY_TIMEOUT_S = 60.0
READY_POLL_S = 0.5


class HubError(RuntimeError):
    """The hub can't be started (already running, uv missing, exited at once) or stopped."""


@dataclass(frozen=True)
class HubRecord:
    """The hub the console started.

    Attributes:
        pid: The top process (uv).
        create_time: psutil's create_time for it, to tell it from a reused pid.
    """

    pid: int
    create_time: float


def start_hub(state_dir: Path) -> HubRecord:
    """Start the voice hub in the background, logging to .state/hub.log.

    Raises:
        HubError: A hub is already running, uv isn't on PATH, or it exited at once.
        OSError: The process couldn't be started.
    """
    if find_console_hub(state_dir) is not None or asyncio.run(is_hub_listening()):
        raise HubError("a voice hub is already running")
    uv = shutil.which("uv")
    if uv is None:
        raise HubError("uv isn't on PATH")
    ensure_state_dir(state_dir)
    env = clean_env(os.environ) | HUB_ENCODING_ENV
    # Forget the old hub before its log is truncated: the server only tails the log while
    # a record exists, so it never reads the new hub's lines under the old record.
    (state_dir / HUB_FILE).unlink(missing_ok=True)
    # Keep the last hub's log (it may say why that hub died); best effort, as a
    # file still held open can't be renamed on Windows.
    with contextlib.suppress(OSError):
        os.replace(state_dir / HUB_LOG_FILE, state_dir / HUB_PREV_LOG_FILE)
    # "wb": each hub gets a fresh log, so the server never replays an old hub's lines.
    with (state_dir / HUB_LOG_FILE).open("wb") as log_file:
        process = spawn_detached([uv, *HUB_ARGS], REPO_ROOT, log_file, env)
    try:
        record = HubRecord(process.pid, psutil.Process(process.pid).create_time())
    except psutil.NoSuchProcess as error:
        raise HubError(f"the hub exited at once; see {state_dir / HUB_LOG_FILE}") from error
    write_json(state_dir / HUB_FILE, {"pid": record.pid, "createTime": record.create_time})
    return record


def wait_for_hub(state_dir: Path, record: HubRecord, timeout_s: float = READY_TIMEOUT_S) -> bool:
    """Wait for the hub start_hub started to listen on its port.

    Returns:
        True once it listens, False if it's still starting after timeout_s.

    Raises:
        HubError: It exited first; the message has the last line of its log.
    """
    deadline = time.monotonic() + timeout_s
    while not asyncio.run(is_hub_listening()):
        if find_recorded_process(record.pid, record.create_time) is None:
            raise HubError(f"the voice hub exited while starting: {_last_log_line(state_dir)}")
        if time.monotonic() >= deadline:
            return False
        time.sleep(READY_POLL_S)
    return True


def _last_log_line(state_dir: Path) -> str:
    # The exception line of a traceback is the log's last line.
    log_path = state_dir / HUB_LOG_FILE
    try:
        lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        lines = []
    last = next((line.strip() for line in reversed(lines) if line.strip()), None)
    return last or f"no output; see {log_path}"


def read_hub_record(state_dir: Path) -> HubRecord | None:
    """The record in .state/hub.json, or None if there is none (or it's malformed)."""
    payload = read_json(state_dir / HUB_FILE)
    pid = payload.get("pid") if payload else None
    create_time = payload.get("createTime") if payload else None
    if not isinstance(pid, int) or not isinstance(create_time, int | float):
        return None
    return HubRecord(pid, float(create_time))


def find_console_hub(state_dir: Path) -> psutil.Process | None:
    """The process of the hub the console started, if it's still running."""
    record = read_hub_record(state_dir)
    return None if record is None else find_recorded_process(record.pid, record.create_time)


def find_hub(record_path: Path = HUB_SELF_RECORD_PATH) -> psutil.Process | None:
    """The hub named by the hub's own record, if that process is still the hub.

    The record's pid and start time must match a running process (so a reused
    pid never counts) whose exe or command line is inside tools/audiohub. The
    recorded pid is the base interpreter, whose command line runs the venv's
    audiohub.exe. The record is only read, never deleted: a stale one reads as
    no hub, and the next hub overwrites it.

    Args:
        record_path: The hub's record (audiohub's `.cache/hub.json`); tests pass their own.
    """
    payload = read_json(record_path)
    pid = payload.get("pid") if payload else None
    create_time = payload.get("create_time") if payload else None
    if not isinstance(pid, int) or not isinstance(create_time, int | float):
        return None
    process = find_recorded_process(pid, create_time)
    return process if process is not None and _runs_from_audiohub(process) else None


def stop_hub(
    state_dir: Path,
    hub_record_path: Path = HUB_SELF_RECORD_PATH,
    request_shutdown: Callable[[], bool] = request_hub_shutdown,
) -> bool:
    """Stop the voice hub: the console's hub, else the one in the hub's record.

    The hub is asked to shut down cleanly first (restoring the music); if it
    doesn't agree, or hasn't exited after GRACEFUL_EXIT_TIMEOUT_S (10 s),
    its own processes are killed.

    The console's record is removed once its hub is dead, or when it names no
    live hub (the hub crashed, or its pid now belongs to another process, which
    is left alone). Then, in the same call, the hub's own record is tried, so a
    crashed console hub followed by a hub started elsewhere takes one Stop. The
    hub's own record is never removed here (see find_hub).

    Args:
        state_dir: The console's .state folder.
        hub_record_path: The hub's own record; tests pass their own.
        request_shutdown: Asks the hub to exit cleanly, True if it agreed;
            tests pass a fake so they never stop a real hub.

    Returns:
        True if a hub was running and was stopped, False if there was none to stop.

    Raises:
        HubError: They couldn't be waited on or killed (e.g. access denied); the console's
            record is kept.
    """
    process = find_console_hub(state_dir)
    if process is None:
        (state_dir / HUB_FILE).unlink(missing_ok=True)
        process = find_hub(hub_record_path)
    if process is None:
        return False
    try:
        has_exited = request_shutdown() and wait_for_exit(process, GRACEFUL_EXIT_TIMEOUT_S)
    except psutil.Error as error:  # e.g. AccessDenied waiting on the hub
        raise HubError(f"couldn't wait for the voice hub (pid {process.pid}): {error}") from error
    if has_exited:
        (state_dir / HUB_FILE).unlink(missing_ok=True)
        return True
    try:
        was_running = _kill_tree(process)
    except psutil.Error as error:
        raise HubError(f"couldn't stop the voice hub (pid {process.pid}): {error}") from error
    (state_dir / HUB_FILE).unlink(missing_ok=True)
    return was_running


def _kill_tree(process: psutil.Process) -> bool:
    """Kill the hub's own processes; False if the hub exited by itself first.

    The hub's own chain is the processes that run from tools/audiohub: uv's
    audiohub.exe launcher, the venv's python.exe redirector, the hub's Python and
    the brain's claude.exe (bundled in the hub's venv). Nothing else under it is
    ours to kill. The brain's MCP servers are stdio children of claude.exe that
    exit when its pipes close, and the daemons they start (the whiteboard and
    sessions daemons, the sleep keeper) are detached on purpose so they outlive
    their starter, so the walk never enters a subtree that isn't the hub's.

    Raises:
        HubError: Part of it survived the kill.
        psutil.Error: A kill was refused.
    """
    try:
        tree = owned_tree(process, _runs_from_audiohub)
    except psutil.NoSuchProcess:
        return False
    alive = kill_processes(tree)
    if alive:
        pids = ", ".join(str(pid) for pid in alive)
        raise HubError(f"voice hub processes still running after the kill: {pids}")
    return True


def _runs_from_audiohub(process: psutil.Process) -> bool:
    # Its exe or a path on its command line is inside tools/audiohub. The command line
    # counts because the hub's Python is the base interpreter, running the venv's audiohub.exe.
    try:
        paths = [process.exe(), *process.cmdline()]
    except psutil.Error:
        return False  # It exited, or isn't ours to inspect: leave it alone.
    return any(Path(path).is_relative_to(AUDIOHUB_ROOT) for path in paths)
