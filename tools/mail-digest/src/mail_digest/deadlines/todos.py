"""Reads the open todos of one week plan, with their due markers and section.

A plan todo looks like `- [ ] [chem-120] A24 Graph Traversal (due 2026-10-23 23:59) (mail)`.
The due marker is `(due YYYY-MM-DD[ HH:MM]` followed by `)`, `;` or `,`, as the KB
conventions write it; a todo with no time is due at the end of that day. Todos
under `## Overdue` are overdue whatever their markers say (they use "was due").
"""

import re
from dataclasses import dataclass
from datetime import date, datetime, time

OPEN_TODO = re.compile(r"\s*[-*+]\s+\[ \]\s+(?P<text>\S.*)")
TAG = re.compile(r"\[(?P<tag>[A-Za-z0-9-]+)\]\s*")
DUE_MARKER = re.compile(r"\(due (?P<day>\d{4}-\d{2}-\d{2})(?: (?P<clock>\d{1,2}:\d{2}))?(?=[);,])")
# One innermost parenthetical: due markers, notes and the (mail)/(site) tag.
PARENTHETICAL = re.compile(r"\([^()]*\)")
# Space left before punctuation where a parenthetical was cut out ("Lab 2 , push").
SPACE_BEFORE_PUNCTUATION = re.compile(r"\s+([,;:.])")
OVERDUE_HEADING = "## overdue"
END_OF_DAY = time(23, 59)


@dataclass(frozen=True)
class PlanTodo:
    """One open todo.

    tag: its course tag without brackets ("" if none).
    name: its text with every parenthetical and the tag removed.
    due: local due time (naive), or None without a readable marker.
    has_time: the marker gave a time (otherwise due is END_OF_DAY).
    is_overdue: it's under `## Overdue`.
    """

    tag: str
    name: str
    due: datetime | None
    has_time: bool
    is_overdue: bool


def open_todos(plan_text: str) -> list[PlanTodo]:
    """Every open `- [ ]` todo in plan_text, in order. Ticked `- [x]` ones are left out."""
    todos, section = [], ""
    for line in plan_text.splitlines():
        if line.startswith("#"):
            section = line.strip().casefold()
            continue
        match = OPEN_TODO.fullmatch(line)
        if match:
            todos.append(_todo(match["text"], section == OVERDUE_HEADING))
    return todos


def _todo(text: str, is_overdue: bool) -> PlanTodo:
    """One todo from the text after its checkbox."""
    tag_match = TAG.match(text)
    tag = tag_match["tag"] if tag_match else ""
    name = text[tag_match.end() :] if tag_match else text
    while PARENTHETICAL.search(name):
        name = PARENTHETICAL.sub("", name)
    name = SPACE_BEFORE_PUNCTUATION.sub(r"\1", " ".join(name.split())).strip(" ,;:.")
    due, has_time = _due(text)
    return PlanTodo(tag, name, due, has_time, is_overdue)


def _due(text: str) -> tuple[datetime | None, bool]:
    """(due time, whether it had a clock time) from the first due marker, or (None, False).

    An impossible date or time (2026-02-30, 25:00) counts as no marker.
    """
    marker = DUE_MARKER.search(text)
    if not marker:
        return None, False
    try:
        day = date.fromisoformat(marker["day"])
        clock = time.fromisoformat(marker["clock"].zfill(5)) if marker["clock"] else END_OF_DAY
    except ValueError:
        return None, False
    return datetime.combine(day, clock), marker["clock"] is not None
