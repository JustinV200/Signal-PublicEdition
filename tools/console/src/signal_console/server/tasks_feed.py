"""Watch tasks.json and usage.json; publish a `tasks` event whenever the Tasks page's data changes.

Both files are polled by mtime at 1 Hz (usage.json's reader rules), and the
payload is rebuilt every REBUILD_S anyway, because a usage window that has
reset changes what the page shows without any write. `tasks` events are
live only (not in the history): a new stream gets current() first.
"""

import asyncio
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from signal_tasks import (
    STATUS_NUMBERS,
    StateFileError,
    Task,
    UsageSummary,
    UsageWindow,
    group_tasks,
    read_tasks,
    read_usage,
)

from signal_console.server.events import EventHub

POLL_S = 1.0
REBUILD_S = 30.0

log = logging.getLogger(__name__)


class TasksFeed:
    """Keeps the Tasks page's payload current and publishes it on change."""

    def __init__(self, events: EventHub, tasks_path: Path, usage_path: Path) -> None:
        """Set up; nothing is read until refresh() or run()."""
        self._events = events
        self._tasks_path = tasks_path
        self._usage_path = usage_path
        self._mtimes: tuple[int | None, int | None] | None = None
        self._built_at = -REBUILD_S
        self._usage: UsageSummary | None = None
        self._payload: dict[str, Any] = {}

    def current(self) -> dict[str, Any]:
        """The latest payload (read fresh if it's due)."""
        self.refresh()
        return self._payload

    async def run(self) -> None:
        """Poll forever (until cancelled), logging and riding out any failed round."""
        while True:
            try:
                self.refresh()
            except Exception:
                log.exception("console tasks poll failed")
            await asyncio.sleep(POLL_S)

    def refresh(self) -> None:
        """Rebuild when a file changed or REBUILD_S passed; publish `tasks` if the payload moved."""
        mtimes = (_mtime_ns(self._tasks_path), _mtime_ns(self._usage_path))
        is_due = time.monotonic() - self._built_at >= REBUILD_S
        if mtimes == self._mtimes and not is_due:
            return
        self._mtimes, self._built_at = mtimes, time.monotonic()
        payload = self._build(datetime.now().astimezone())
        if payload != self._payload:
            self._payload = payload
            self._events.publish("tasks", payload)

    def _build(self, now: datetime) -> dict[str, Any]:
        try:
            task_list = read_tasks(self._tasks_path)
        except StateFileError as error:
            log.warning("keeping the last tasks: %s", error)  # retried next tick
            self._mtimes = None
            return self._payload
        # None means usage.json is mid-replace or bad: keep the last good copy.
        self._usage = read_usage(self._usage_path, now) or self._usage
        groups = group_tasks(task_list.tasks)
        return {
            "updatedAt": task_list.updated_at,
            "active": [_task(task) for task in groups.active],
            "queued": [_task(task) for task in groups.queued],
            "done": [_task(task) for task in groups.done],
            "needsYou": groups.needs_you,
            "overallPct": groups.overall_pct,
            "usage": _usage(self._usage),
        }


def _task(task: Task) -> dict[str, Any]:
    return {
        "id": task.id,
        "name": task.name,
        "pct": task.pct,
        "status": task.status,
        "number": STATUS_NUMBERS[task.status],
        "next": task.next,
        "you": task.you,
        "updatedAt": task.updated_at,
    }


def _usage(usage: UsageSummary | None) -> dict[str, Any] | None:
    if usage is None:
        return None
    return {
        "fiveHour": _window(usage.five_hour),
        "sevenDay": _window(usage.seven_day),
        "agents": usage.agents,
        "updatedAt": usage.updated_at.isoformat() if usage.updated_at else None,
    }


def _window(window: UsageWindow | None) -> dict[str, Any] | None:
    if window is None:
        return None
    return {"usedPct": window.used_pct, "resetsAt": window.resets_at.isoformat()}


def _mtime_ns(path: Path) -> int | None:
    try:
        return path.stat().st_mtime_ns
    except OSError:
        return None
