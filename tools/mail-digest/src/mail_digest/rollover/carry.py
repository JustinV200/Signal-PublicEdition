"""Works out what moves from last week's plan to the new one, and what was done.

The rules (life/README.md), all deterministic:

- Open `- [ ]` todos move over, marked `carried from <MM-DD>` (the Monday of the week
  they were first carried out of); their indented lines move with them. A todo
  already marked carried keeps its mark, so it's never marked twice.
- Todos under `## Overdue` stay under `## Overdue`.
- An open todo whose `(due ...)` day (on its own line, not an indented one) is before
  the rollover's day is late, so it moves to `## Overdue`, its marker reworded to
  `(was due ...)` as the KB writes it. Today's own todos aren't late yet, whatever
  their time (a date-only due counts as 23:59), so a mid-week rollover (the PC was
  off on Monday) still moves Monday-to-yesterday's todos. A marker that isn't a real
  date (2026-02-30) counts as no due date.
- Ticked `- [x]` todos stay behind; they're listed as done in last week's review.
- Nothing is ever ticked or dropped, except an open line that's exactly one of the
  template's own placeholder todos (the new plan gets a fresh copy of those).
"""

import re
from dataclasses import dataclass
from datetime import date, timedelta

from mail_digest.deadlines import DUE_MARKER
from mail_digest.rollover.sections import Section, split_sections
from mail_digest.rollover.weeks import DAYS_PER_WEEK

# Leading spaces allowed: an open subtask under a ticked todo still moves (on its own).
OPEN_TODO = re.compile(r"\s*[-*+] \[ \] ")
TICKED_TODO = re.compile(r"[-*+] \[[xX]\] ")
OVERDUE = "## Overdue"
# Where open todos above the first `## ` heading go.
UNSECTIONED = "## Other"
# Already marked: "(carried)", "(carried; ...)", "(...; carried)" or "(..., carried ...)".
CARRIED_MARK = re.compile(r"[(;,] ?carried\b")
# The first-carry mark, whose date says how long a todo has been carried.
CARRIED_FROM = re.compile(r"carried from (?P<month>\d{2})-(?P<day>\d{2})\b")
# Todos carried this many weeks or more are listed in last week's review.
STALE_WEEKS = 3
# The first due parenthetical's text up to its `)`, where "; carried from" goes.
DUE_PARENTHETICAL = re.compile(r"\((?:was )?due [^()]*(?=\))")
# The trailing source tag (` (mail)`, ` (site)`), which must stay last on the line.
SOURCE_TAG = re.compile(r" \((?:mail|site)\)\s*$")


@dataclass(frozen=True)
class Carry:
    """What a rollover moves and leaves behind.

    overdue: items for the new `## Overdue`, old ones first, then newly late ones.
    by_section: (heading, items) for every other section, in plan order.
    done: the ticked todo lines left behind.
    stale: first lines of carried todos marked carried STALE_WEEKS or more weeks ago.
    Each item is its todo line plus any indented lines under it, joined by \\n.
    """

    overdue: tuple[str, ...]
    by_section: tuple[tuple[str, tuple[str, ...]], ...]
    done: tuple[str, ...]
    stale: tuple[str, ...] = ()

    @property
    def items(self) -> tuple[str, ...]:
        """Every carried item, Overdue first."""
        return (*self.overdue, *(item for _, items in self.by_section for item in items))

    @property
    def count(self) -> int:
        """How many todos move over in all."""
        return len(self.items)


def collect_carry(
    plan_text: str, source_monday: date, today: date, placeholders: frozenset[str]
) -> Carry:
    """Sort last week's plan into what moves over and what was done.

    source_monday: last week's Monday, for the `carried from` mark. today: the
    rollover's day, which lateness and carried age are judged against. placeholders:
    the template's own todo lines, stripped.
    """
    plan = split_sections(plan_text)
    loose = Section(UNSECTIONED, [line for line in plan.preamble if line.strip()])
    old_overdue: list[str] = []
    late: list[str] = []
    by_section: dict[str, list[str]] = {}
    done: list[str] = []
    for section in [loose, *plan.sections]:
        is_overdue = section.key == Section(OVERDUE).key
        for item in _open_items(section.lines, placeholders):
            due = DUE_MARKER.search(_first_line(item))
            if is_overdue:
                old_overdue.append(mark_carried(item, source_monday))
            elif due and _is_before(due["day"], today):
                was_due = f"{item[: due.start()]}(was {item[due.start() + 1 :]}"
                late.append(mark_carried(was_due, source_monday))
            else:
                marked = mark_carried(item, source_monday)
                by_section.setdefault(section.heading, []).append(marked)
        done += [line.strip() for line in section.lines if TICKED_TODO.match(line)]
    sections = tuple((heading, tuple(items)) for heading, items in by_section.items())
    carry = Carry(tuple(old_overdue + late), sections, tuple(done))
    stale = tuple(_first_line(item) for item in carry.items if _is_stale(item, today))
    return Carry(carry.overdue, sections, carry.done, stale)


def mark_carried(item: str, source_monday: date) -> str:
    """The item with `carried from <MM-DD>` on its first line, unless it's carried already.

    It goes inside the due parenthetical (`(due 2026-11-12 10:00; carried from 11-02)`),
    else in its own `(carried from 11-02)` before the source tag, so ` (mail)` or
    ` (site)` stays last.
    """
    first, *rest = item.split("\n")
    if not CARRIED_MARK.search(first):
        mark = f"carried from {source_monday:%m-%d}"
        due = DUE_PARENTHETICAL.search(first)
        tag = SOURCE_TAG.search(first)
        if due:
            first = f"{first[: due.end()]}; {mark}{first[due.end() :]}"
        elif tag:
            first = f"{first[: tag.start()]} ({mark}){first[tag.start() :]}"
        else:
            first = f"{first.rstrip()} ({mark})"
    return "\n".join([first, *rest])


def _first_line(item: str) -> str:
    """The todo line itself, without its indented lines."""
    return item.split("\n", 1)[0]


def _is_before(day: str, today: date) -> bool:
    """True if day (YYYY-MM-DD) is a real date before today. An impossible date is False."""
    try:
        return date.fromisoformat(day) < today
    except ValueError:
        return False


def _is_stale(item: str, today: date) -> bool:
    """True if the item's `carried from MM-DD` is STALE_WEEKS or more weeks before today.

    The mark has no year, so it's the latest such date on or before today. A plain
    `carried` mark (no date) or an impossible date is never stale.
    """
    match = CARRIED_FROM.search(_first_line(item))
    if not match:
        return False
    try:
        since = date(today.year, int(match["month"]), int(match["day"]))
        if since > today:
            since = since.replace(year=today.year - 1)
    except ValueError:
        return False
    return today - since >= timedelta(days=STALE_WEEKS * DAYS_PER_WEEK)


def _open_items(lines: list[str], placeholders: frozenset[str]) -> list[str]:
    """The open todos among lines, each with the indented lines that follow it."""
    items: list[list[str]] = []
    is_collecting = False
    for line in lines:
        if is_collecting and line[:1] in (" ", "\t") and line.strip():
            items[-1].append(line.rstrip())
            continue
        is_collecting = bool(OPEN_TODO.match(line)) and line.strip() not in placeholders
        if is_collecting:
            items.append([line.strip()])
    return ["\n".join(item) for item in items]
