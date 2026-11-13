"""The runner's last step on the items: merge repeats, then work out overdue and due soon.

The same assignment can be on two pages (Moodle's assignment index and its calendar),
so items are merged by course and link (built from the ref): a trusted status beats
unknown, and two trusted ones that disagree give unknown (on Classroom, the worse
list wins instead, see _merge). Then overdue is "on Classroom's missing list, or open (not
submitted) and due before now", never for an unknown status, and due soon is "not
done, not overdue, and due in the next DUE_SOON". A due date with no time counts as
the end of that day.
"""

from dataclasses import replace
from datetime import datetime, time, timedelta

from mail_digest.assignment_check.courses import CLASSROOM
from mail_digest.assignment_check.findings.model import DONE, MISSING, OPEN, UNKNOWN, Item

DUE_SOON = timedelta(hours=24)
# Classroom's lists, worst first wins when one item is on two of them.
CLASSROOM_RANK = {DONE: 0, OPEN: 1, MISSING: 2}
DATE_ONLY_CHARS = len("YYYY-MM-DD")
END_OF_DAY = time(23, 59)


def flagged(items: list[Item], now: datetime) -> tuple[Item, ...]:
    """items merged by (course, link) and flagged against now (timezone-aware, local).

    The link is built from the item's ref, so two items with the same name stay two.
    """
    merged: dict[tuple[str, str], Item] = {}
    for item in items:
        key = (item.course, item.link)
        merged[key] = _merge(merged[key], item) if key in merged else item
    return tuple(_flag(item, now) for item in merged.values())


def _merge(known: Item, item: Item) -> Item:
    """One item seen twice. A trusted status beats unknown; two trusted ones must agree.

    The one exception is Classroom, where the same work on two lists means the
    lists moved between page loads: the worse one wins (missing, then not turned
    in, then turned in), so done never beats open or missing. Any other
    disagreement makes the status unknown. Whichever copy is kept, a due date the
    other copy has fills in a missing one (the unknown copy often carries it).
    """
    kept = _pick(known, item)
    if kept.due:
        return kept
    return replace(kept, due=known.due or item.due)


def _pick(known: Item, item: Item) -> Item:
    """The copy whose status wins (see _merge)."""
    if item.status == UNKNOWN or item.status == known.status:
        return known
    if known.status == UNKNOWN:
        return item
    if known.site == item.site == CLASSROOM:
        return max(known, item, key=lambda i: CLASSROOM_RANK[i.status])
    return replace(known, status=UNKNOWN)


def _flag(item: Item, now: datetime) -> Item:
    """item with overdue and due_soon set."""
    if item.status == DONE:
        return item
    due = due_at(item.due, now)
    # Only a status the runner trusts as not handed in can be overdue: an unknown one
    # (no Moodle phrase on its row, a quiz, a calendar event) may well be submitted.
    is_past = due is not None and due < now
    overdue = item.status == MISSING or (item.status == OPEN and is_past)
    due_soon = not overdue and due is not None and now <= due <= now + DUE_SOON
    return replace(item, overdue=overdue, due_soon=due_soon)


def due_at(due: str, now: datetime) -> datetime | None:
    """due (findings.items' normalised form) as a datetime in now's timezone, or None."""
    if not due:
        return None
    if len(due) == DATE_ONLY_CHARS:
        day = datetime.strptime(due, "%Y-%m-%d").date()
        return datetime.combine(day, END_OF_DAY, tzinfo=now.tzinfo)
    return datetime.strptime(due, "%Y-%m-%d %H:%M").replace(tzinfo=now.tzinfo)
