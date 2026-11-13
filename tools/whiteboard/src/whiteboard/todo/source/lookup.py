"""find_entries: resolve what the owner or Claude typed ("A19", an item id) to todo lines.

Used by done/undone. A board cross-out names its item by id only; the owner and Claude
may also give a piece of the text. An item can have more than one line, e.g. the same task under
`## Overdue` and under its course; they share an id, and all of them are returned
so their checkboxes stay in step.
"""

from collections.abc import Sequence

from whiteboard.todo.source.plan_lines import PlanEntry

_MAX_LISTED = 5


class TodoLookupError(LookupError):
    """No todo matches, or more than one item does."""


def find_entries(entries: Sequence[PlanEntry], ref: str, by_text: bool = True) -> list[PlanEntry]:
    """Every line of the one item `ref` names.

    Args:
        entries: The latest parse of this and next week's plans.
        ref: An item id, or a piece of "[tag] text" (case-insensitive) that only one item has.
        by_text: False to accept only an exact id (no text search).

    Raises:
        TodoLookupError: Empty ref, no match, or several different items match.
    """
    needle = ref.strip().lower()
    if not needle:
        raise TodoLookupError("name the todo item: its id or a piece of its text")
    by_id = [entry for entry in entries if entry.id == needle]
    if by_id:
        return by_id
    if not by_text:
        raise TodoLookupError(f"no todo item has the id {ref!r}")
    hits = [entry for entry in entries if needle in f"[{entry.tag}] {entry.text}".lower()]
    ids = list(dict.fromkeys(entry.id for entry in hits))
    if len(ids) == 1:
        return hits
    if not ids:
        raise TodoLookupError(f"no todo item matches {ref!r}")
    names = "; ".join(_label(next(e for e in hits if e.id == i)) for i in ids[:_MAX_LISTED])
    raise TodoLookupError(f"{len(ids)} todo items match {ref!r}, say which: {names}")


def _label(entry: PlanEntry) -> str:
    """An item as `<id> [tag] text`, for listing candidates."""
    return f"{entry.id} [{entry.tag}] {entry.text}"
