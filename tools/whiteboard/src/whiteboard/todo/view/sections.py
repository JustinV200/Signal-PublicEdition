"""build_groups: sort parsed todo lines into what the TODO view shows, in order.

1. Overdue: items in the plan's `## Overdue` section that are undated or past due
   (one re-dated to today or later shows on that day), plus any open item whose due
   day has passed wherever it sits. Only open items late by at most OVERDUE_RECENT_DAYS
   show, newest first, at most MAX_OVERDUE_ROWS; the rest (older, undated, past the
   cap) are folded into the heading ("Overdue · +2 older") so they can't crowd out
   what's due now. Items done today in the group still show, after the open ones.
2. Today, then Tomorrow, then This week (the rest of the WINDOW_DAYS window), each by
   date and time (untimed last on a day).
3. Work items of note: items in `## Of note` due after the window, or with no date.
Everything else (done and past due outside Overdue, further out, undated) isn't shown.
Done items stay in place (struck through) unless the caller hides them. Each row has
a short title (titles.short_title) and its due text (labels.due_label).
"""

from collections.abc import Collection, Sequence
from dataclasses import dataclass
from datetime import date, timedelta

from whiteboard.todo.source import SECTION_OF_NOTE, SECTION_OVERDUE, PlanEntry
from whiteboard.todo.view.labels import (
    GROUP_OF_NOTE,
    GROUP_OVERDUE,
    GROUP_TODAY,
    GROUP_TOMORROW,
    GROUP_WEEK,
    day_label,
    due_label,
)
from whiteboard.todo.view.titles import short_title

# Today plus this many days: a deadline a week from today (same weekday) still shows.
WINDOW_DAYS = 7
# Overdue items later than this many days are folded into the heading's count.
OVERDUE_RECENT_DAYS = 7
MAX_OVERDUE_ROWS = 5
GROUP_ORDER = (GROUP_OVERDUE, GROUP_TODAY, GROUP_TOMORROW, GROUP_WEEK, GROUP_OF_NOTE)
_FIXED_LABELS = {
    GROUP_OVERDUE: "Overdue",
    GROUP_WEEK: "This week",
    GROUP_OF_NOTE: "Work items of note",
}


@dataclass(frozen=True)
class GroupRow:
    """One item in a group: its plan entry, its short title and its due text."""

    entry: PlanEntry
    due_label: str
    title: str


@dataclass(frozen=True)
class TodoGroup:
    """A heading and its items.

    Attributes:
        key: One of GROUP_ORDER.
        label: The heading text.
        rows: The items in display order.
        folded: Overdue items left out of rows (counted in the label).
    """

    key: str
    label: str
    rows: tuple[GroupRow, ...]
    folded: tuple[PlanEntry, ...] = ()


def build_groups(
    entries: Sequence[PlanEntry], today: date, hidden_ids: Collection[str] = ()
) -> list[TodoGroup]:
    """Group and sort entries for the board; empty groups are left out.

    Args:
        entries: This week's entries, then next week's. When one item (same id) is
            placed twice, the later line wins, so next week's copy of a carried item counts.
        today: The board's today.
        hidden_ids: Items not to show (done before today).
    """
    placed: dict[str, tuple[str, PlanEntry]] = {}
    for entry in entries:
        key = _group_key(entry, today)
        if key is not None and entry.id not in hidden_ids:
            placed[entry.id] = (key, entry)
    by_key: dict[str, list[PlanEntry]] = {}
    for key, entry in placed.values():
        by_key.setdefault(key, []).append(entry)
    groups = []
    for key in (key for key in GROUP_ORDER if key in by_key):
        if key == GROUP_OVERDUE:
            shown, folded = _split_overdue(by_key[key], today)
        else:
            shown, folded = sorted(by_key[key], key=_sort_key), []
        rows = tuple(_row(entry, key, today) for entry in shown)
        groups.append(TodoGroup(key, _label(key, today, len(folded)), rows, tuple(folded)))
    return groups


def _row(entry: PlanEntry, key: str, today: date) -> GroupRow:
    """A GroupRow; a text that's all struck-through parts keeps its full text."""
    return GroupRow(entry, due_label(entry, key, today), short_title(entry.text) or entry.text)


def _split_overdue(
    entries: list[PlanEntry], today: date
) -> tuple[list[PlanEntry], list[PlanEntry]]:
    """(rows to show, open items folded into the heading); see the module docstring."""
    oldest_shown = today - timedelta(days=OVERDUE_RECENT_DAYS)
    open_items = [entry for entry in entries if not entry.is_done]
    recent = [e for e in open_items if e.due is not None and e.due.day >= oldest_shown]
    # Newest first: the ones still worth saving lead.
    recent.sort(key=_sort_key, reverse=True)
    shown = recent[:MAX_OVERDUE_ROWS]
    folded = [entry for entry in open_items if entry not in shown]
    done_today = [entry for entry in entries if entry.is_done]
    return shown + done_today, folded


def _group_key(entry: PlanEntry, today: date) -> str | None:
    """Which group an entry belongs in, or None if the view doesn't show it."""
    due = entry.due
    # A line under `## Overdue` that has since been given a new date, today or later,
    # shows on that day instead (never as "0d late").
    if entry.section == SECTION_OVERDUE and (due is None or due.day < today):
        return GROUP_OVERDUE
    # Overdue is a fact of the date, not of where the line was filed.
    if due is not None and due.day < today and not entry.is_done:
        return GROUP_OVERDUE
    if due is not None and today <= due.day <= today + timedelta(days=WINDOW_DAYS):
        if due.day == today:
            return GROUP_TODAY
        return GROUP_TOMORROW if due.day == today + timedelta(days=1) else GROUP_WEEK
    is_further_out = due is None or due.day > today + timedelta(days=WINDOW_DAYS)
    if entry.section == SECTION_OF_NOTE and is_further_out:
        return GROUP_OF_NOTE
    return None


def _sort_key(entry: PlanEntry) -> tuple[bool, date, str]:
    """Dated items by date and time; undated ones last. sorted() keeps plan order on ties."""
    if entry.due is None:
        return (True, date.max, "")
    day, time = entry.due.sort_key
    return (False, day, time)


def _label(key: str, today: date, folded_count: int) -> str:
    """The heading for a group key."""
    if key == GROUP_TODAY:
        return f"Today · {day_label(today)}"
    if key == GROUP_TOMORROW:
        return f"Tomorrow · {day_label(today + timedelta(days=1))}"
    label = _FIXED_LABELS[key]
    return f"{label} · +{folded_count} older" if folded_count else label
