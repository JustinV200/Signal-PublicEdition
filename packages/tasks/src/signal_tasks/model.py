"""One task in tasks.json: its fields, their limits, and the checks on them.

tasks.json is written by the orchestrator through `console tasks set` and read
by the console page and the whiteboard grid, so every field is checked on the
way in, and a hand-edited entry that fails the checks is skipped on the way out.
"""

import re
from dataclasses import asdict, dataclass
from typing import Any

# The board's status numbers (the whiteboard-task-grid layout). Every display shows
# the number and the word, not a colour, so it also works for colourblind users.
STATUS_NUMBERS: dict[str, int] = {
    "review": 1,
    "building": 2,
    "needs_you": 3,
    "queued": 4,
    "done": 5,
}
STATUS_WORDS: dict[str, str] = {
    "review": "review",
    "building": "building",
    "needs_you": "needs you",
    "queued": "queued",
    "done": "done",
}
ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9.-]{0,39}$")
MAX_NAME_CHARS = 60
MAX_NEXT_CHARS = 140
MAX_YOU_CHARS = 200
MIN_PCT, MAX_PCT = 0, 100
# Any control character (newlines included) would break a one-line display.
_CONTROL = re.compile(r"[\x00-\x1f\x7f]")


class TaskError(ValueError):
    """A task field is missing or breaks its rule; the message names the field."""


@dataclass(frozen=True)
class Task:
    """One unit of work the orchestrator reports.

    Attributes:
        id: Short slug (ID_PATTERN), unique in the file.
        name: What the task is, shown as the row's title.
        pct: Rough percent done, 0-100.
        status: One of STATUS_NUMBERS.
        next: The next step, one line ("" if none).
        you: What the owner must do; required while status is needs_you.
        updated_at: ISO time of the last change (local, with offset).
    """

    id: str
    name: str
    pct: int
    status: str
    next: str
    you: str
    updated_at: str


def check_task(task: Task) -> Task:
    """Return `task` if every field keeps its rule.

    Raises:
        TaskError: Naming the first bad field.
    """
    if not ID_PATTERN.fullmatch(task.id):
        raise TaskError(f"id must match {ID_PATTERN.pattern} (lowercase letters, digits, - .)")
    _check_text("name", task.name, MAX_NAME_CHARS, required=True)
    _check_text("next", task.next, MAX_NEXT_CHARS)
    _check_text("you", task.you, MAX_YOU_CHARS)
    # bool is an int subclass; True must not pass as 1%.
    if isinstance(task.pct, bool) or not isinstance(task.pct, int):
        raise TaskError("pct must be a whole number")
    if not MIN_PCT <= task.pct <= MAX_PCT:
        raise TaskError(f"pct must be {MIN_PCT} to {MAX_PCT}")
    if task.status not in STATUS_NUMBERS:
        raise TaskError(f"status must be one of {', '.join(STATUS_NUMBERS)}")
    if task.status == "needs_you" and not task.you.strip():
        raise TaskError("a needs_you task must say what the owner has to do (--you)")
    return task


def task_from_dict(raw: Any) -> Task:
    """Build and check a Task from one tasks.json entry.

    Raises:
        TaskError: Not an object, a missing field, or a field that breaks its rule.
    """
    if not isinstance(raw, dict):
        raise TaskError("a task must be a JSON object")
    try:
        task = Task(
            id=raw["id"],
            name=raw["name"],
            pct=raw["pct"],
            status=raw["status"],
            next=raw.get("next", ""),
            you=raw.get("you", ""),
            updated_at=raw.get("updated_at", ""),
        )
    except KeyError as error:
        raise TaskError(f"a task is missing {error.args[0]}") from error
    if not isinstance(task.updated_at, str):
        raise TaskError("updated_at must be a string")
    return check_task(task)


def task_to_dict(task: Task) -> dict[str, Any]:
    """The task as a tasks.json entry."""
    return asdict(task)


def _check_text(field: str, value: Any, max_chars: int, *, required: bool = False) -> None:
    if not isinstance(value, str):
        raise TaskError(f"{field} must be text")
    if required and not value.strip():
        raise TaskError(f"{field} can't be empty")
    if len(value) > max_chars:
        raise TaskError(f"{field} is longer than {max_chars} characters")
    if _CONTROL.search(value):
        raise TaskError(f"{field} must be one line with no control characters")
