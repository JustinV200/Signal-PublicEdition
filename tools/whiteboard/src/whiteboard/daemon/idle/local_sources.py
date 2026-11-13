"""LocalSources: the idle regions read from files, rebuilt only when a file changed.

Files: this and next week's plans in life/ (TODAY, PRIORITIES and the plan side of
UPCOMING), the TODO view's done-tracking (which ticked items still show), the console's
tasks.json and tools/usage's usage.json (AGENTS and the usage line), the calendar's
agenda cache (UPCOMING), and today's keynotes (KEYNOTES, none when stale or missing).
A refresh compares their modification times, the date, and a
REREAD_MIN-minute bucket (so ended events, reset usage windows and a stale agenda drop
off without a file change) with the last one, and reads nothing if they all match.
Each source fails on its own: its regions keep their last data, and the outage is
logged once. Blocking: the controller runs refresh() in a thread.
"""

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from signal_jsonstate import StateFileError
from signal_tasks import group_tasks, read_tasks, read_usage

from whiteboard.daemon.idle.outages import Outages
from whiteboard.idle import (
    DatedItem,
    agents_region,
    overdue_count,
    read_agenda,
    read_priorities,
    today_rows,
    upcoming_items,
    upcoming_rows,
    usage_line,
)
from whiteboard.keynotes import read_keynotes
from whiteboard.todo import WINDOW_DAYS, TodoStore, build_groups, read_week_entries, track
from whiteboard.todo.source import find_week_plans, read_plan

# Re-read everything at least this often, even with no file changed.
REREAD_MIN = 5
_WEEK = timedelta(days=7)


@dataclass(frozen=True)
class IdleFiles:
    """Where the idle view reads from and caches into.

    Attributes:
        life_dir: The owner's KB (repo root / "life").
        todo_state_path: The TODO view's .state/todo.json (read-only here).
        tasks_path: The console's tasks.json.
        usage_path: tools/usage's usage.json.
        agenda_path: tools/calendar's agenda.json.
        cache_dir: .state/idle/, for the weather and location caches.
        keynotes_path: .state/keynotes.json (read-only), or None for no keynotes.
    """

    life_dir: Path
    todo_state_path: Path
    tasks_path: Path
    usage_path: Path
    agenda_path: Path
    cache_dir: Path
    keynotes_path: Path | None = None


class LocalSources:
    """The file-backed regions; see the module docstring."""

    def __init__(self, files: IdleFiles, labels: dict[str, str], outages: Outages) -> None:
        """Args:
        files: Where to read.
        labels: Chip names (whiteboard.idle.parse_tag_labels).
        outages: Logs each source's outage once.
        """
        self._files = files
        self._labels = labels
        self._outages = outages
        self._signature: tuple[Any, ...] | None = None
        self._plan_upcoming: list[DatedItem] = []
        self._agenda: list[DatedItem] = []
        self._regions: dict[str, Any] = {
            "tasks": [],
            "overdue": 0,
            "notes": [],
            "keynotes": [],
            "upcoming": [],
            "agents": None,
            "usage": None,
        }

    def refresh(self, now: datetime, force: bool = False) -> dict[str, Any] | None:
        """Re-read the files if anything changed (or `force`).

        Args:
            now: Local time now (aware).
            force: Read even if nothing seems changed (a manual sync).

        Returns:
            The file-backed regions, or None when nothing was read.
        """
        signature = self._signature_for(now)
        if signature == self._signature and not force:
            return None
        self._signature = signature
        today = now.date()
        last_day = today + timedelta(days=WINDOW_DAYS)
        self._read_plans(today, last_day)
        self._read_tasks(now)
        self._read_agenda(now, last_day)
        if self._files.keynotes_path is not None:
            self._regions["keynotes"] = list(read_keynotes(self._files.keynotes_path, today))
        self._regions["upcoming"] = upcoming_rows([*self._plan_upcoming, *self._agenda], today)
        return dict(self._regions)

    def _signature_for(self, now: datetime) -> tuple[Any, ...]:
        """The date, the re-read bucket and every source file's mtime."""
        files = self._files
        plans = [plan.path for plan in find_week_plans(files.life_dir, now.date())]
        paths = [
            *plans,
            files.todo_state_path,
            files.tasks_path,
            files.usage_path,
            files.agenda_path,
            *([files.keynotes_path] if files.keynotes_path else []),
        ]
        bucket = (now.hour * 60 + now.minute) // REREAD_MIN
        return (now.date(), bucket, tuple((path, _mtime_ns(path)) for path in paths))

    def _read_plans(self, today: date, last_day: date) -> None:
        """TODAY, PRIORITIES and the plan side of UPCOMING."""
        try:
            entries, plans = read_week_entries(self._files.life_dir, today)
            result = track(entries, TodoStore(self._files.todo_state_path).load(), today)
            groups = build_groups(entries, today, result.hidden_ids)
            this_week = [plan for plan in plans if plan.monday <= today < plan.monday + _WEEK]
            notes = []
            if this_week:
                markdown = read_plan(this_week[0].path).text
                notes = read_priorities(markdown, this_week[0].monday, today, self._labels)
        except (OSError, UnicodeDecodeError) as error:
            self._outages.failed("week plans", error)
            return
        self._outages.ok("week plans")
        self._regions["tasks"] = today_rows(groups, today, result.done_ids, self._labels)
        self._regions["overdue"] = overdue_count(groups, result.done_ids)
        self._regions["notes"] = notes
        self._plan_upcoming = upcoming_items(entries, today, last_day, self._labels)

    def _read_tasks(self, now: datetime) -> None:
        """AGENTS and the usage line; an unreadable usage file keeps the last line."""
        try:
            groups = group_tasks(read_tasks(self._files.tasks_path).tasks)
        except StateFileError as error:
            self._outages.failed("agent tasks", error)
        else:
            self._outages.ok("agent tasks")
            self._regions["agents"] = agents_region(groups)
        usage = read_usage(self._files.usage_path, now)
        if usage is not None:
            self._regions["usage"] = usage_line(usage)

    def _read_agenda(self, now: datetime, last_day: date) -> None:
        """The calendar side of UPCOMING."""
        try:
            self._agenda = read_agenda(self._files.agenda_path, now, last_day)
        except StateFileError as error:
            self._outages.failed("calendar agenda", error)
        else:
            self._outages.ok("calendar agenda")


def _mtime_ns(path: Path) -> int | None:
    """The file's modification time, or None if it's missing or can't be read."""
    try:
        return path.stat().st_mtime_ns
    except OSError:
        return None
