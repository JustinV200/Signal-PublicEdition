"""start_whiteboard_if_down: start the whiteboard daemon for sleep when it isn't running.

Sleep calls this when the night view can't be shown. The daemon, once up, puts the
night view on by itself (tools/whiteboard daemon/night_resume.py reads sleepmode's
state file), and the keeper's night guard uncovers the projector once it shows. The
whiteboard stays standalone: this runs its own CLI (`whiteboard serve`, the command its
MCP server starts) through uv, never its code, and returns without waiting for it.
"""

import logging
import subprocess
from pathlib import Path

from sleepmode.shared import popen_detached
from sleepmode.whiteboard_link.discovery import read_live_daemon_info

log = logging.getLogger(__name__)

# The whiteboard's own daemon log, the one its MCP server's starts append to.
DAEMON_LOG_FILE = "daemon.log"
# Past this a log moves to daemon.log.1 before a start, like the whiteboard's own starts.
LOG_ROTATE_BYTES = 5 * 1024 * 1024
DAEMON_FLAGS = subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP


def whiteboard_serve_command(whiteboard_root: Path) -> list[str]:
    """`uv run` of the whiteboard's `serve` command in its own project and venv."""
    return ["uv", "run", "--project", str(whiteboard_root), "--frozen", "whiteboard", "serve"]


def start_whiteboard_if_down(state_dir: Path, whiteboard_root: Path) -> bool:
    """Start the whiteboard daemon detached unless daemon.json names a running one.

    Args:
        state_dir: The whiteboard's .state/ folder (daemon.json, daemon.log).
        whiteboard_root: tools/whiteboard (the uv project and working directory).

    Returns:
        True if a daemon was started, False if one was already running.

    Raises:
        OSError: The daemon couldn't be started (uv missing, the log unwritable, ...).
    """
    # Missing, unreadable or stale counts as down: a second daemon only fails to claim
    # the port and exits, which costs nothing.
    if read_live_daemon_info(state_dir) is not None:
        return False
    state_dir.mkdir(parents=True, exist_ok=True)
    log.info("the whiteboard daemon isn't running; starting it for the night view")
    log_path = state_dir / DAEMON_LOG_FILE
    _rotate_log(log_path)
    # The child keeps its own copy of the handle, so closing ours right away is fine.
    with open(log_path, "ab") as daemon_log:
        command = whiteboard_serve_command(whiteboard_root)
        popen_detached(command, DAEMON_FLAGS, whiteboard_root, daemon_log)
    return True


def _rotate_log(log_path: Path) -> None:
    """Move a log past LOG_ROTATE_BYTES to <name>.1, replacing the previous one.

    Runs only when no daemon is up, so nothing holds the file open. A failure is
    logged and the old log just keeps growing.
    """
    try:
        if log_path.stat().st_size > LOG_ROTATE_BYTES:
            log_path.replace(log_path.with_name(log_path.name + ".1"))
    except FileNotFoundError:
        return
    except OSError as error:
        log.warning("couldn't rotate %s: %s", log_path, error)
