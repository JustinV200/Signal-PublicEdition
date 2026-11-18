"""The rows about what the console needs beside itself: the built page, Edge, the whiteboard,
and the voice hub's log. Each is a file read; nothing is started or asked over the network.
"""

import time
from pathlib import Path

import psutil

from signal_console.health.inputs import HealthPaths
from signal_console.health.row import ATTENTION, FAIL, OK, RECENT_WINDOW, SETUP_COMMAND, HealthRow
from signal_console.paths import HUB_LOG_FILE
from signal_console.state_files import read_json
from signal_console.status import WHITEBOARD_DAEMON_FILE, parse_hub_line

# Only the end of hub.log is read: its last run's errors are near the end.
HUB_LOG_TAIL_BYTES = 64 * 1024
HUB_ERROR_PREFIX = "error:"


def web_build_row(paths: HealthPaths) -> HealthRow:
    """Fail when the page isn't built (web/dist/index.html is missing)."""
    if (paths.web_dist_dir / "index.html").is_file():
        return HealthRow("web-build", "Console page", OK, "built", "The console's page is built.")
    words = "The console's page isn't built, so the window shows only a placeholder."
    fix = "Build it with setup, then run console open again."
    return HealthRow("web-build", "Console page", FAIL, "not built", words, fix, SETUP_COMMAND)


def edge_row(paths: HealthPaths) -> HealthRow:
    """Fail when msedge.exe isn't where `console open` starts it."""
    if paths.edge_path.is_file():
        return HealthRow(
            "edge", "Microsoft Edge", OK, "found", "Edge is installed for the console window."
        )
    words = f"Edge isn't at {paths.edge_path}, so console open can't make the console's window."
    fix = "Install Microsoft Edge (it comes with Windows), then run console open again."
    return HealthRow("edge", "Microsoft Edge", FAIL, "missing", words, fix)


def whiteboard_row(paths: HealthPaths) -> HealthRow:
    """Attention when the whiteboard daemon isn't running (daemon.json's process is gone)."""
    daemon = read_json(paths.whiteboard_dir / WHITEBOARD_DAEMON_FILE) or {}
    if _is_daemon_running(daemon.get("pid"), daemon.get("started_at")):
        words = f"The whiteboard is running on port {daemon.get('port')}."
        return HealthRow("whiteboard", "Whiteboard", OK, "running", words)
    words = "The whiteboard isn't running, so the Boards page and the camera are empty."
    fix = "It starts by itself the next time Claude uses the whiteboard."
    return HealthRow("whiteboard", "Whiteboard", ATTENTION, "off", words, fix)


def hub_log_row(paths: HealthPaths) -> HealthRow:
    """Attention when the voice hub's log, written in the last 24 hours, holds errors."""
    log_path = paths.state_dir / HUB_LOG_FILE
    try:
        is_recent = time.time() - log_path.stat().st_mtime < RECENT_WINDOW.total_seconds()
        errors = _count_errors(log_path)
    except FileNotFoundError:
        words = "The console hasn't started Voice yet, so there's no log."
        return HealthRow("hub-log", "Voice log", OK, "no log", words)
    except OSError as error:
        words = f"Voice's log can't be read ({type(error).__name__})."
        fix = f"Check that {log_path} isn't locked or blocked, then run console doctor again."
        return HealthRow("hub-log", "Voice log", ATTENTION, "unreadable", words, fix)
    if not (errors and is_recent):
        words = "No errors in Voice's log from the last 24 hours."
        return HealthRow("hub-log", "Voice log", OK, "no errors", words)
    words = f"Voice logged {errors} errors near the end of its log."
    fix = f"Read {log_path} for the reason, then start voice again from the Voice page."
    return HealthRow("hub-log", "Voice log", ATTENTION, "errors", words, fix)


def _is_daemon_running(pid: object, started_at: object) -> bool:
    # The daemon writes started_at (time.time()) just after it starts, so its own process
    # began before then; a process that reused the pid began later. A file without
    # started_at is malformed (the whiteboard always writes it), so it reads as off.
    if not isinstance(pid, int) or isinstance(pid, bool) or not isinstance(started_at, int | float):
        return False
    try:
        return psutil.Process(pid).create_time() <= started_at
    except psutil.Error:
        return False  # No such process, or it can't be read: not ours to count as running.


def _count_errors(log_path: Path) -> int:
    with log_path.open("rb") as log_file:
        size = log_file.seek(0, 2)
        log_file.seek(max(0, size - HUB_LOG_TAIL_BYTES))
        tail = log_file.read().decode("utf-8", errors="replace")
    lines = (parse_hub_line(line) for line in tail.splitlines())
    return sum(1 for line in lines if line and line.text.startswith(HUB_ERROR_PREFIX))
