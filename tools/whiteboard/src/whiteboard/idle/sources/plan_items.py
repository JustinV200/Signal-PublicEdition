"""The TODAY region and the plan side of UPCOMING, from the week plans' todo lines.

Built on the TODO view's own grouping (todo.view.build_groups), so both views agree:
- TODAY: the newest OVERDUE_SLOTS overdue items (the TODO view already folds old
  ones away; overdue_count gives the whole count for the heading), then today's items
  (by time, untimed last), then the next days' open items until SLOTS are used. Items
  ticked before today are hidden (the TODO view's tracking); one ticked today stays,
  struck through, says "✓ done", and is dropped first when there are more rows than
  SLOTS, before any open item. Rows show the TODO view's short titles.
- UPCOMING: open dated items from tomorrow to the window's end, for upcoming_rows.
Read-only: the idle view never ticks anything.
"""

from collections.abc import Collection, Mapping, Sequence
from datetime import date
from typing import Any

from whiteboard.idle.chips import chip
from whiteboard.idle.sources.upcoming import DatedItem, short_day
from whiteboard.todo.source import PlanEntry
from whiteboard.todo.view import (
    DONE_LABEL,
    GROUP_OF_NOTE,
    GROUP_OVERDUE,
    GROUP_TODAY,
    GroupRow,
    TodoGroup,
    short_title,
)

# The region's rows (design.md section 2). The page turns a longer list into "+N more".
SLOTS = 6
# Overdue rows on the idle view, so they can't crowd out today's.
OVERDUE_SLOTS = 2
WHEN_OVERDUE = "overdue"
WHEN_TODAY = "today"
WHEN_LATER = "later"
# A deadline at the end of the day reads as a date, not a time.
END_OF_DAY_TIMES = ("23:59", "24:00")


def today_rows(
    groups: Sequence[TodoGroup], today: date, done_ids: Collection[str], labels: Mapping[str, str]
) -> list[dict[str, Any]]:
    """The TODAY region's rows (see the module docstring).

    Args:
        groups: build_groups(entries, today, hidden_ids), done-before-today already hidden.
        today: The board's today.
        done_ids: Items with a ticked box (shown struck through).
        labels: Chip names (chips.parse_tag_labels).
    """
    must: list[dict[str, Any]] = []
    later: list[dict[str, Any]] = []
    for group in groups:
        if group.key == GROUP_OF_NOTE:
            continue
        when = _when(group.key)
        rows = group.rows[:OVERDUE_SLOTS] if when == WHEN_OVERDUE else group.rows
        for row in rows:
            item = _task(row, when, today, row.entry.id in done_ids, labels)
            if when == WHEN_LATER:
                if not item["done"]:
                    later.append(item)
            else:
                must.append(item)
    # Done rows give way to open ones, the next days' included.
    must = _drop_done_past(must, max(0, SLOTS - len(later)))
    return must + later[: max(0, SLOTS - len(must))]


def overdue_count(groups: Sequence[TodoGroup], done_ids: Collection[str]) -> int:
    """Every open overdue item, shown or folded, for the TODAY heading's count."""
    for group in groups:
        if group.key == GROUP_OVERDUE:
            shown = sum(1 for row in group.rows if row.entry.id not in done_ids)
            return shown + len(group.folded)
    return 0


def upcoming_items(
    entries: Sequence[PlanEntry], today: date, last_day: date, labels: Mapping[str, str]
) -> list[DatedItem]:
    """Open dated plan items from tomorrow to `last_day`, outside the Overdue section.

    Args:
        entries: This and next week's parsed lines.
        today: The board's today (today's items are in TODAY instead).
        last_day: The window's last day.
        labels: Chip names.
    """
    items = []
    seen: set[str] = set()
    # Later lines win, like build_groups: next week's copy of a carried item counts.
    for entry in reversed(entries):
        due = entry.due
        if entry.is_done or due is None or entry.id in seen or not today < due.day <= last_day:
            continue
        seen.add(entry.id)
        time = None if due.time in END_OF_DAY_TIMES else due.time
        title = short_title(entry.text) or entry.text
        # The time goes into the title, unless the title already says it.
        text = f"{title} {time}" if time and time not in title else title
        items.append(DatedItem(due.day, time, chip(entry.tag, labels), text))
    return items


def _when(group_key: str) -> str:
    """Which due colour a group's rows get."""
    if group_key == GROUP_OVERDUE:
        return WHEN_OVERDUE
    return WHEN_TODAY if group_key == GROUP_TODAY else WHEN_LATER


def _task(
    row: GroupRow, when: str, today: date, is_done: bool, labels: Mapping[str, str]
) -> dict[str, Any]:
    """One row: chip, short title, the due column (or "✓ done"), done."""
    entry = row.entry
    if is_done:
        due = DONE_LABEL
    elif when == WHEN_OVERDUE:
        due = row.due_label  # "3d late", as on the TODO view
    elif when == WHEN_TODAY:
        time = entry.due.time if entry.due else None
        due = time if time and time not in END_OF_DAY_TIMES else WHEN_TODAY
    else:
        due = short_day(entry.due.day, today) if entry.due else ""
    return {
        "id": entry.id,
        "chip": chip(entry.tag, labels),
        "text": row.title,
        "due": due,
        "when": when,
        "done": is_done,
    }


def _drop_done_past(rows: list[dict[str, Any]], slots: int) -> list[dict[str, Any]]:
    """Drop done rows, last first, while there are more rows than slots."""
    rows = list(rows)
    for index in range(len(rows) - 1, -1, -1):
        if len(rows) <= slots:
            break
        if rows[index]["done"]:
            del rows[index]
    return rows
