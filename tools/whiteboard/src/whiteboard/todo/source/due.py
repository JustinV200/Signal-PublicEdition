"""Due dates in week-plan todo lines: find the "(due ...)" note in a line and read its date.

Formats in use (life/README.md and the week plans):
- `(due 2026-10-21 08:30)` and `(due 2026-10-19)`, 24-hour clock.
- `(was due 2026-10-15 17:00; notes)` and `(were due 2026-08-27, 2026-08-31; notes)`,
  in `## Overdue`. The first date counts.
- `(due Thu)` or `(due Thursday 17:00)`: that weekday of the plan's own week.

Anything after the date (`;`, `,` or more words) is a note and is ignored. A due
note whose date can't be read, e.g. `(due date TODO: verify)`, gives no due date,
but the note is still taken out of the text shown on the board.
"""

import re
from dataclasses import dataclass
from datetime import date, timedelta

# "(due ...)", "(was due ...)" or "(were due ...)"; plan notes never nest parentheses.
_DUE_NOTE = re.compile(r"\(\s*(?:(?:was|were)\s+)?due\s+(?P<spec>[^()]*)\)", re.IGNORECASE)
_ISO_DATE = re.compile(r"(?P<date>\d{4}-\d{2}-\d{2})(?:\s+(?P<time>\d{1,2}:\d{2}))?\b")
_WORD_AND_TIME = re.compile(r"(?P<word>[A-Za-z]+)\.?(?:\s+(?P<time>\d{1,2}:\d{2}))?\b")
_SPACE_BEFORE_PUNCTUATION = re.compile(r"\s+([,.;:!?])")
WEEKDAY_NAMES = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")
# A weekday may be shortened, but to at least its first three letters ("thu", "thurs").
_MIN_WEEKDAY_LETTERS = 3
_LAST_HOUR = 23
_LAST_MINUTE = 59
# Sorts after every real time, so untimed items come last on their day (due by day's end).
END_OF_DAY = "24:00"


@dataclass(frozen=True)
class Due:
    """When an item is due.

    Attributes:
        day: The due date.
        time: "HH:MM" on the 24-hour clock, or None when only a date was given.
    """

    day: date
    time: str | None = None

    @property
    def sort_key(self) -> tuple[date, str]:
        """Order by date, then time, with untimed items last on their day."""
        return (self.day, self.time or END_OF_DAY)


def split_due(text: str, week_monday: date) -> tuple[Due | None, str]:
    """Find the due note in a todo's text and return its date plus the text without it.

    Args:
        text: The todo text after the checkbox and tag.
        week_monday: Monday of the plan's week, for weekday-only dates like "Thu".

    Returns:
        (due or None, the text with the first due note removed and spacing tidied).
    """
    match = _DUE_NOTE.search(text)
    if match is None:
        return None, _tidy(text)
    shown = _tidy(text[: match.start()] + text[match.end() :])
    return parse_due_spec(match["spec"], week_monday), shown


def parse_due_spec(spec: str, week_monday: date) -> Due | None:
    """Read the date at the start of a due note's body ("2026-10-21 08:30; ...", "Thu").

    Returns:
        The Due, or None if the body doesn't start with a readable date.
    """
    spec = spec.strip()
    iso = _ISO_DATE.match(spec)
    if iso is not None:
        try:
            return Due(date.fromisoformat(iso["date"]), _clock(iso["time"]))
        except ValueError:
            return None
    named = _WORD_AND_TIME.match(spec)
    if named is None:
        return None
    weekday = _weekday_index(named["word"])
    if weekday is None:
        return None
    return Due(week_monday + timedelta(days=weekday), _clock(named["time"]))


def _weekday_index(word: str) -> int | None:
    """0 for Monday ... 6 for Sunday, or None if `word` isn't a (shortened) weekday."""
    word = word.lower()
    if len(word) < _MIN_WEEKDAY_LETTERS:
        return None
    for index, name in enumerate(WEEKDAY_NAMES):
        if name.startswith(word):
            return index
    return None


def _clock(raw: str | None) -> str | None:
    """Normalize "8:30" to "08:30"; None for a missing or impossible time."""
    if raw is None:
        return None
    hours, minutes = (int(part) for part in raw.split(":"))
    if hours > _LAST_HOUR or minutes > _LAST_MINUTE:
        return None
    return f"{hours:02d}:{minutes:02d}"


def _tidy(text: str) -> str:
    """Collapse runs of spaces and drop spaces left in front of punctuation."""
    collapsed = " ".join(text.split())
    return _SPACE_BEFORE_PUNCTUATION.sub(r"\1", collapsed).strip(" ;,")
