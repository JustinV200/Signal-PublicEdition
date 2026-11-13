"""TodoStore: keep the TODO view's DoneTracking in .state/todo.json across daemon restarts.

The file is `{"done_since": {"<id>": "YYYY-MM-DD"}, "open_ids": ["<id>", ...]}`.
Losing it only costs a little: items done earlier show struck through for one more
day, and one cross-out animation may be skipped. So an unreadable file is logged
and replaced by an empty memory instead of stopping the daemon.
"""

import json
import logging
from datetime import date
from pathlib import Path
from typing import Any

from whiteboard.shared import write_atomically
from whiteboard.todo.view.tracking import DoneTracking

log = logging.getLogger(__name__)


class TodoStore:
    """Loads and saves one todo.json."""

    def __init__(self, path: Path) -> None:
        """Args: path: The file, usually STATE_DIR / "todo.json". Its folder is made on save."""
        self.path = path

    def load(self) -> DoneTracking:
        """The stored memory, or an empty one if there's no file or it's invalid."""
        if not self.path.is_file():
            return DoneTracking()
        try:
            return _tracking_from_dict(json.loads(self.path.read_text(encoding="utf-8")))
        except (OSError, ValueError, TypeError, AttributeError, KeyError) as error:
            log.warning("todo state %s is unreadable (%s); starting fresh", self.path, error)
            return DoneTracking()

    def save(self, tracking: DoneTracking) -> None:
        """Write the memory atomically.

        Raises:
            OSError: The file can't be written.
        """
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "done_since": {item: day.isoformat() for item, day in tracking.done_since.items()},
            "open_ids": sorted(tracking.open_ids),
        }
        write_atomically(self.path, json.dumps(data, indent=1).encode("utf-8"))


def _tracking_from_dict(data: Any) -> DoneTracking:
    """Validate the JSON shape.

    Raises:
        ValueError, TypeError, AttributeError or KeyError: on anything but the documented shape.
    """
    done_since = {str(item): date.fromisoformat(day) for item, day in data["done_since"].items()}
    open_ids = data["open_ids"]
    if not isinstance(open_ids, list) or not all(isinstance(item, str) for item in open_ids):
        raise ValueError("open_ids must be a list of strings")
    return DoneTracking(done_since, frozenset(open_ids))
