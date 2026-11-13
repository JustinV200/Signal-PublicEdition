"""AuditLog: a line in .state/todo.log (and the daemon log) for every checkbox the board changes.

Ticking a box in life/ is the whiteboard's only write to the owner's KB, so each one
is recorded with when, who asked, the item and the exact plan line.
"""

import logging
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from whiteboard.daemon.todo.summary import relative_path
from whiteboard.todo import PlanEntry

logger = logging.getLogger(__name__)


class AuditLog:
    """Appends one line per edit; a failed append is logged, never raised."""

    def __init__(self, path: Path, repo_root: Path, clock: Callable[[], datetime]) -> None:
        """Args:
        path: The log file, e.g. .state/todo.log.
        repo_root: Plan paths are written relative to this.
        clock: Local time now.
        """
        self._path = path
        self._repo_root = repo_root
        self._clock = clock

    def record(self, action: str, entry: PlanEntry, source: str) -> None:
        """Record that `entry` was marked `action` ("done"/"undone") because of `source`."""
        where = f"{relative_path(entry.source.path, self._repo_root)}:{entry.source.line_no + 1}"
        line = f"{action} ({source}): [{entry.tag}] {entry.text} -- {where}"
        logger.info("TODO view: %s", line)
        stamp = self._clock().isoformat(timespec="seconds")
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with self._path.open("a", encoding="utf-8") as audit:
                audit.write(f"{stamp} {line}\n")
        except OSError as error:
            # The plan edit itself went through; a lost audit line isn't worth failing it.
            logger.error("TODO view: couldn't append to %s: %s", self._path, error)
