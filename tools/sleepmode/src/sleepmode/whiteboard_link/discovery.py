"""read_live_daemon_info: the whiteboard daemon's daemon.json, if it names a running daemon.

Shared by the night view client (night_view, for the port) and the daemon start
(daemon_start, to leave a running daemon alone). The whiteboard writes daemon.json
({pid, port}) on start and removes it on a clean exit; a crash leaves it behind.
"""

import json
from pathlib import Path
from typing import Any

from sleepmode.shared import is_process_alive

DAEMON_INFO_FILE = "daemon.json"


def read_live_daemon_info(state_dir: Path) -> dict[str, Any] | None:
    """daemon.json's contents, or None unless it's a JSON object whose int pid is running.

    Args:
        state_dir: The whiteboard's .state/ folder.
    """
    try:
        info = json.loads((state_dir / DAEMON_INFO_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(info, dict):
        return None
    pid = info.get("pid")
    # A crashed daemon's leftover file: connecting to its port would cost ~2 s.
    return info if isinstance(pid, int) and is_process_alive(pid) else None
