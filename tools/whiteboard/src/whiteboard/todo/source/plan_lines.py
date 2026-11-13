"""parse_plan: turn a week plan's markdown into PlanEntry records, one per todo line.

A todo line is `- [ ] [tag] text (due ...)` or `- [x] ...` (life/README.md). Each
entry remembers its `##` section (Overdue, Of note, or any other), its due date
(due.py), and the exact source line, so the board can tick that line later and
refuse if it changed. Numbered lists (Priorities) and plain text are ignored.
split_recurring then gives each date of a recurring item its own id.
"""

import hashlib
import re
from collections.abc import Sequence
from dataclasses import dataclass, replace
from datetime import date
from pathlib import Path

from whiteboard.todo.source.due import Due, split_due

SECTION_OVERDUE = "overdue"
SECTION_OF_NOTE = "of_note"
SECTION_OTHER = "other"

_HEADING = re.compile(r"^(?P<hashes>#{1,6})\s+(?P<title>.*?)[\s#]*$")
_TODO = re.compile(r"^\s*[-*+]\s+\[(?P<mark>[ xX])\]\s+(?P<rest>.*\S)\s*$")
_TAG = re.compile(r"^\[(?P<tag>[^\[\]]+)\]\s*(?P<text>.*)$")
# `#` is the page title and `##` a section; `###` and deeper stay inside their section.
_SECTION_LEVEL = 2
_ID_HEX_CHARS = 12


@dataclass(frozen=True)
class SourceLine:
    """Where an entry came from.

    Attributes:
        path: The plan file.
        line_no: 0-based index into PlanText.lines().
        text: The whole line as read, without its line ending.
    """

    path: Path
    line_no: int
    text: str


@dataclass(frozen=True)
class PlanEntry:
    """One todo line.

    Attributes:
        id: Stable across syncs: a hash of the tag and the shown text, so ticking the
            box or editing the due note keeps it. A recurring item's lines also hash
            their due date (split_recurring).
        section: SECTION_OVERDUE, SECTION_OF_NOTE or SECTION_OTHER.
        tag: The course or area, e.g. "chem-120" ("" if the line has none).
        text: The text to show, without the due note.
        due: The due date, or None.
        is_done: Whether the box is ticked.
        source: The exact line, for edits.
    """

    id: str
    section: str
    tag: str
    text: str
    due: Due | None
    is_done: bool
    source: SourceLine


def parse_plan(markdown: str, path: Path, week_monday: date) -> list[PlanEntry]:
    """Every todo line in a plan, in file order.

    Args:
        markdown: The plan's text (PlanText.text).
        path: The plan file, recorded in each entry's source.
        week_monday: Monday of the plan's week, for weekday-only due dates.
    """
    section = SECTION_OTHER
    entries: list[PlanEntry] = []
    for line_no, line in enumerate(markdown.splitlines()):
        heading = _HEADING.match(line)
        if heading is not None:
            if len(heading["hashes"]) <= _SECTION_LEVEL:
                section = _section_of(heading["title"], len(heading["hashes"]))
            continue
        entry = _entry(line, SourceLine(path, line_no, line), section, week_monday)
        if entry is not None:
            entries.append(entry)
    return entries


def item_id(tag: str, text: str, due_day: date | None = None) -> str:
    """The stable id for a tag and shown text (case and spacing don't matter).

    Args:
        tag: The line's tag.
        text: The shown text.
        due_day: Only for a recurring item's lines (split_recurring), else None.
    """
    key = f"{tag.lower()}|{' '.join(text.lower().split())}"
    if due_day is not None:
        key += f"|{due_day.isoformat()}"
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:_ID_HEX_CHARS]


def split_recurring(entries: Sequence[PlanEntry]) -> list[PlanEntry]:
    """Give each due date of a recurring item its own id; other entries are unchanged.

    Lines with the same tag and text are one item, so an item's `## Overdue` copy, or
    its copy carried into next week's plan, ticks with the original even when the due
    note differs or is missing. But when those lines fall on two or more due dates
    outside Overdue ("Reading (due Tue)", "Reading (due Thu)"), they're separate tasks,
    and each dated line's id adds its date. An Overdue copy with one of those dates
    then still matches that day's line.

    shortcut: an undated copy of a recurring item keeps the plain id and shows as its
    own row, since nothing says which date it belongs to.

    Args:
        entries: Every line parsed from this and next week's plans.
    """
    days_by_id: dict[str, set[date]] = {}
    for entry in entries:
        if entry.due is not None and entry.section != SECTION_OVERDUE:
            days_by_id.setdefault(entry.id, set()).add(entry.due.day)
    recurring = {item for item, days in days_by_id.items() if len(days) > 1}
    return [
        replace(entry, id=item_id(entry.tag, entry.text, entry.due.day))
        if entry.id in recurring and entry.due is not None
        else entry
        for entry in entries
    ]


def _section_of(title: str, level: int) -> str:
    """Which section a heading starts; the page title (`#`) resets to none."""
    name = " ".join(title.lower().split())
    if level < _SECTION_LEVEL:
        return SECTION_OTHER
    if name == "overdue":
        return SECTION_OVERDUE
    # "## Of note" (the convention), also "## Work items of note".
    if name.endswith("of note"):
        return SECTION_OF_NOTE
    return SECTION_OTHER


def _entry(line: str, source: SourceLine, section: str, week_monday: date) -> PlanEntry | None:
    """The PlanEntry for a todo line, or None for any other line (or an empty todo)."""
    todo = _TODO.match(line)
    if todo is None:
        return None
    rest = todo["rest"]
    tagged = _TAG.match(rest)
    tag, body = (tagged["tag"].strip(), tagged["text"]) if tagged else ("", rest)
    due, text = split_due(body, week_monday)
    if not text:
        return None
    return PlanEntry(
        id=item_id(tag, text),
        section=section,
        tag=tag,
        text=text,
        due=due,
        is_done=todo["mark"] != " ",
        source=source,
    )
