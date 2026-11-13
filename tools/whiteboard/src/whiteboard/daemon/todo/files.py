"""TodoFiles: where the daemon's TODO view reads and keeps its files."""

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class TodoFiles:
    """Where the TODO view reads and keeps things.

    Attributes:
        life_dir: The owner's KB (repo root / "life").
        state_path: The done-tracking memory, .state/todo.json.
        audit_path: Every checkbox the board changed, .state/todo.log.
        keynotes_path: Today's keynotes, .state/keynotes.json (read-only; none when absent).
    """

    life_dir: Path
    state_path: Path
    audit_path: Path
    keynotes_path: Path | None = None
