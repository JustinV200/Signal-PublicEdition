"""The TODO rows a board cross-out is matched against, built from the view's layout.

TodoController lays the view out; the StrikeWatcher (strike_watch.py) matches new ink
against these rows. Each open row becomes a StrikeTarget: where it is on the board,
the row as projected ("[tag] text (due ...)"), and the rows just above and below it,
so the model check can tell apart two items with the same text under different tags.
A row whose neighbour has the same text is flagged (has_twin): its cross-out only hints.
row_spots is what those targets depend on: while it stays the same, a line drawn
under one layout lands on the same rows in the next.
"""

from collections.abc import Collection, Sequence

from whiteboard.todo import RowPlace, StrikeTarget, TodoLayout


def row_spots(layout: TodoLayout) -> tuple[object, ...]:
    """Each row's item, due text and place: what a cross-out is matched against.

    Ticking an item leaves this as it was (the row stays put, dimmed). A moved, added,
    removed or re-worded row, or a new board size, changes it.
    """
    return tuple(
        (place.row.entry.id, place.row.due_label, place.box, place.text_x, place.ink_w)
        for place in layout.rows
    )


def open_targets(layout: TodoLayout, done_ids: Collection[str]) -> list[StrikeTarget]:
    """The rows not yet done, as StrikeTargets (see the module docstring)."""
    rows = layout.rows
    return [
        _target(rows, index, layout.metrics.font_px)
        for index, place in enumerate(rows)
        if place.row.entry.id not in done_ids
    ]


def _target(rows: Sequence[RowPlace], index: int, font_px: float) -> StrikeTarget:
    """rows[index] as a StrikeTarget, with its neighbours in the same column as context."""
    place = rows[index]
    box = place.box
    above, below = (_neighbour(rows, near, box.x) for near in (index - 1, index + 1))
    return StrikeTarget(
        id=place.row.entry.id,
        x0=place.text_x,
        x1=place.text_x + place.ink_w,
        y0=box.y,
        y1=box.y + box.h,
        font_px=font_px,
        row_x0=box.x,
        row_x1=box.x + box.w,
        text=_shown_text(place),
        above=_shown_text(above) if above else "",
        below=_shown_text(below) if below else "",
        has_twin=any(near is not None and _has_same_words(near, place) for near in (above, below)),
    )


def _neighbour(rows: Sequence[RowPlace], index: int, column_x: float) -> RowPlace | None:
    """rows[index] if it exists and sits in the column at `column_x`, else None."""
    # Rows run down one column, then the next: the row before a column's first is
    # the bottom of the column to its left, not the row above it.
    if 0 <= index < len(rows) and rows[index].box.x == column_x:
        return rows[index]
    return None


def _has_same_words(first: RowPlace, second: RowPlace) -> bool:
    """Whether two rows' shown titles read the same (ignoring case and spacing)."""
    return first.row.title.casefold().split() == second.row.title.casefold().split()


def _shown_text(place: RowPlace) -> str:
    """A row as the page shows it: "[tag] title (due ...)", leaving out a missing tag or due."""
    entry, due_label = place.row.entry, place.row.due_label
    tag = f"[{entry.tag}] " if entry.tag else ""
    due = f" (due {due_label})" if due_label else ""
    return f"{tag}{place.row.title}{due}"
