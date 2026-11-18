"""One health row: a check's level, its state in a word or two, a sentence, and how to fix it.

Every check in this package returns one. `console doctor` prints them and
`GET /api/health` sends them as JSON, so the shape is the contract between the
two (and with the setup tool's rows, which take the same shape later).
"""

from dataclasses import asdict, dataclass
from datetime import timedelta
from typing import Any, Literal

# ok: nothing to do. attention: the console works, but something needs a look.
# fail: the console can't work until it's fixed (doctor exits 1).
Level = Literal["ok", "attention", "fail"]
OK: Level = "ok"
ATTENTION: Level = "attention"
FAIL: Level = "fail"

# The fix for what setup builds or writes (the page, the hooks); runs from the repo root.
SETUP_COMMAND = r".\setup.cmd console"
# Hook and hub errors newer than this count as a problem; older ones are history.
RECENT_WINDOW = timedelta(hours=24)


@dataclass(frozen=True)
class HealthRow:
    """One check's result.

    Attributes:
        id: Stable id, e.g. "turn-hook".
        name: What was checked, in words ("Turn hook").
        level: ok, attention or fail.
        state: The state in a word or two ("running", "missing").
        words: One sentence on what was found.
        fix: For a row that isn't ok, one plain sentence on what to do; else None.
        command: A full command that fixes it, runnable as shown, or None.
    """

    id: str
    name: str
    level: Level
    state: str
    words: str
    fix: str | None = None
    command: str | None = None

    def as_json(self) -> dict[str, Any]:
        """The row as the JSON object /api/health sends."""
        return asdict(self)
