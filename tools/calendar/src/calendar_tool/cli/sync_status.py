"""The last `sync-cache` outcome in .state/sync_status.json, so a failed scheduled run is visible.

The scheduled task runs under pythonw, where stderr goes nowhere. This file is what
`calendar setup` (and later the board) reads to say why the agenda stopped updating:
{"ok": bool, "at": ISO 8601, "kind": error class name, "message": safe error text},
plus "skipped": [calendar names] when a successful sync couldn't read some calendars.
"""

from datetime import datetime
from pathlib import Path

from signal_jsonstate import StateFileError, read_json_object, write_json_atomic

from calendar_tool.errors import CalendarError


def record_sync_status(
    path: Path, at: datetime, error: CalendarError | None = None, skipped: list[str] | None = None
) -> None:
    """Save the outcome. A failed save is ignored: it must never hide the sync's own result.

    Args:
        path: Usually paths.SYNC_STATUS_PATH.
        at: When the sync ran (aware).
        error: The failure, or None for success. str(error) is secret-free (errors.py).
        skipped: Calendars a successful sync couldn't read; saved only when non-empty.
    """
    status = {"ok": error is None, "at": at.isoformat(timespec="seconds")}
    if error is not None:
        status |= {"kind": type(error).__name__, "message": str(error)}
    if skipped:
        status["skipped"] = skipped
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        write_json_atomic(path, status)
    except (OSError, StateFileError):
        pass


def describe_sync_status(path: Path) -> str:
    """One line for `calendar setup`: when the last sync ran and whether it worked."""
    try:
        status = read_json_object(path)
    except StateFileError:
        return "unreadable"
    if not status:
        return "never run"
    if status.get("ok"):
        skipped = status.get("skipped")
        note = f" (skipped: {', '.join(map(str, skipped))})" if isinstance(skipped, list) else ""
        return f"OK at {status.get('at')}{note}"
    return f"FAILED at {status.get('at')}: {status.get('kind')}: {status.get('message')}"
