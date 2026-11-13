"""Shared test helpers: temp state paths, fixed local times, quick appends."""

from datetime import datetime
from pathlib import Path

from signal_brief import BriefPaths, NewEntry, append_entry

UNDO = {"tool": "Bash", "args": {"command": "git revert 1a2b3c4"}}


def make_paths(tmp_path: Path) -> BriefPaths:
    """State in tmp_path/.state, and a sleepmode file that doesn't exist (awake)."""
    return BriefPaths(tmp_path / ".state", tmp_path / "sleep-state.json")


def at(day: int, hour: int, minute: int = 0) -> datetime:
    """A local, aware time in October 2026 (the 20th is a Tuesday)."""
    return datetime(2026, 10, day, hour, minute).astimezone()


def log(paths: BriefPaths, kind: str, title: str, now: datetime, **fields: object):
    """Append one entry; decisions get UNDO unless given another."""
    if kind == "decision":
        fields.setdefault("undo", UNDO)
    return append_entry(paths, NewEntry(kind, title, **fields), now)  # type: ignore[arg-type]
