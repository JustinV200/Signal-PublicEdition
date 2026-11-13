"""short_title: a plan line's text cut down to a short, scannable title for the board.

Plan lines carry notes meant for the agents that keep them, not for a glance across
the room: source tags such as "(site)" and "(mail)", long parentheticals listing files
or status, struck-through done parts ("~~Reading 1 video~~ done 2026-10-09."), and clauses
after a comma or colon. The rules, in order, all deterministic:
1. Struck-through parts are dropped, with a "done <date>" note right after them.
2. Every parenthetical longer than SHORT_NOTE_CHARS is dropped, wherever it sits.
3. Trailing source tags (SOURCE_TAGS: "(site)", "(mail)", ...) are dropped. Other short
   notes, like "(attend)", stay.
4. A title still over MAX_TITLE_CHARS is cut at its first clause break (", ", "; ",
   ": ", " - ", " – ", " — ") that keeps MIN_HEAD_CHARS to MAX_TITLE_CHARS, so the
   kept part still says what the item is ("Check A3, A5, A7, A9 in Classroom", not
   "Check A3"). With no such break it's cut at the last space within MAX_TITLE_CHARS
   and ends in an ellipsis.
"""

import re

MAX_TITLE_CHARS = 40
# A clause break only ends the title when the part before it is at least this long.
MIN_HEAD_CHARS = 20
# A parenthetical up to this long ("(attend)", "(Ch 6)") is part of the title.
SHORT_NOTE_CHARS = 12
# The source tags the plans end lines with (life/README.md's convention), lowercase.
SOURCE_TAGS = ("site", "mail", "email", "cal", "web")
ELLIPSIS = "…"

_STRUCK = re.compile(r"~~[^~]*~~(?:\s+done(?:\s+\d{4}-\d{2}-\d{2})?)?[.;,]?")
_PARENTHETICAL = re.compile(r"\s*\([^()]*\)")
_TRAILING_TAG = re.compile(r"\s*\(\s*(?:" + "|".join(SOURCE_TAGS) + r")\s*\)\s*$", re.IGNORECASE)
_CLAUSE_BREAKS = (", ", "; ", ": ", " - ", " – ", " — ")
_SPACE_BEFORE_PUNCTUATION = re.compile(r"\s+([,.;:!?])")
_EDGE_PUNCTUATION = " ,;:.-–—+&"


def short_title(text: str) -> str:
    """The board title for a plan line's text (see the module docstring).

    Args:
        text: The line's text, due note already taken out.

    Returns:
        The title; "" when the whole text was struck-through done parts.
    """
    title = _tidy(_STRUCK.sub(" ", text))
    title = _tidy(_PARENTHETICAL.sub(_keep_short, title))
    while (stripped := _TRAILING_TAG.sub("", title)) != title:
        title = _tidy(stripped)
    if len(title) > MAX_TITLE_CHARS:
        title = _cut(title)
    return title


def _keep_short(match: re.Match[str]) -> str:
    """A parenthetical kept when short, else dropped (re.sub callback)."""
    note = match.group(0)
    return note if len(note.strip()) <= SHORT_NOTE_CHARS else " "


def _cut(title: str) -> str:
    """The first clause that fits MIN_HEAD_CHARS..MAX_TITLE_CHARS, else a word cut and "…"."""
    breaks = [title.find(mark, MIN_HEAD_CHARS) for mark in _CLAUSE_BREAKS]
    fitting = [index for index in breaks if 0 <= index <= MAX_TITLE_CHARS]
    if fitting:
        return title[: min(fitting)].strip(_EDGE_PUNCTUATION)
    space = title.rfind(" ", 0, MAX_TITLE_CHARS + 1)
    # One very long word: cut it mid-word rather than keep almost nothing.
    end = space if space >= MIN_HEAD_CHARS else MAX_TITLE_CHARS
    return title[:end].strip(_EDGE_PUNCTUATION) + ELLIPSIS


def _tidy(text: str) -> str:
    """Collapse spaces, drop spaces before punctuation, trim punctuation at the ends."""
    collapsed = _SPACE_BEFORE_PUNCTUATION.sub(r"\1", " ".join(text.split()))
    return collapsed.strip(_EDGE_PUNCTUATION)
