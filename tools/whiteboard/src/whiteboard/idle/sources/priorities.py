"""The PRIORITIES region: the first lines of this week plan's `## Priorities` list.

A fixed rule, no model (the owner confirmed it): the numbered lines under `## Priorities`,
in order, skipping a line whose `(due ...)` notes are all before today, at most SLOTS.
A line with no readable due note always counts. The due notes are taken out of the
text and the rest goes through the TODO view's short_title (struck-through done parts,
long notes and source tags dropped); a line with nothing left (all done) is skipped.
A leading `[tag]` becomes the chip.
"""

import re
from collections.abc import Mapping
from datetime import date
from typing import Any

from whiteboard.idle.chips import chip
from whiteboard.todo.source import Due, split_due
from whiteboard.todo.view import short_title

SLOTS = 3
_HEADING = re.compile(r"^(#{1,6})\s+(.*?)[\s#]*$")
_NUMBERED = re.compile(r"^\s*\d+[.)]\s+(?P<rest>.*\S)\s*$")
_TAG = re.compile(r"^\[(?P<tag>[^\[\]]+)\]\s*(?P<text>.*)$")
SECTION_TITLE = "priorities"
# `##` is a section; a deeper heading stays inside it.
_SECTION_LEVEL = 2


def read_priorities(
    markdown: str, week_monday: date, today: date, labels: Mapping[str, str]
) -> list[dict[str, Any]]:
    """The region's rows: [{chip, text}], at most SLOTS.

    Args:
        markdown: This week's plan.md.
        week_monday: Its Monday, for weekday-only due notes ("due Thu").
        today: Lines whose due dates are all before this are skipped.
        labels: Chip names.
    """
    rows = []
    for line in _section_lines(markdown):
        numbered = _NUMBERED.match(line)
        if numbered is None:
            continue
        tagged = _TAG.match(numbered["rest"])
        tag, body = (tagged["tag"].strip(), tagged["text"]) if tagged else ("", numbered["rest"])
        dues, text = _strip_due_notes(body, week_monday)
        title = short_title(text)
        if not title or (dues and all(due.day < today for due in dues)):
            continue
        rows.append({"chip": chip(tag, labels), "text": title})
        if len(rows) == SLOTS:
            break
    return rows


def _section_lines(markdown: str) -> list[str]:
    """The lines under `## Priorities`, up to the next section heading."""
    lines: list[str] = []
    inside = False
    for line in markdown.splitlines():
        heading = _HEADING.match(line)
        if heading is not None and len(heading[1]) <= _SECTION_LEVEL:
            if inside:
                break
            inside = " ".join(heading[2].lower().split()) == SECTION_TITLE
            continue
        if inside:
            lines.append(line)
    return lines


def _strip_due_notes(text: str, week_monday: date) -> tuple[list[Due], str]:
    """Every readable due date in the text, and the text with every due note taken out."""
    dues: list[Due] = []
    while True:
        due, shorter = split_due(text, week_monday)
        if due is not None:
            dues.append(due)
        # split_due only tidies spacing when there's no note left, so this ends.
        if shorter == text:
            return dues, text
        text = shorter
