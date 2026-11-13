"""normalize_event: one raw Calendar API event -> the idle board's small AgendaEvent.

Timed events are converted to local time (or a given zone); all-day events keep
their dates. Only the start, end, all-day flag, a cleaned and capped title and
the calendar name survive: event text comes from whoever sent the invite, so
nothing else is kept.
"""

import re
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime, time, tzinfo
from typing import Any

MAX_TITLE_CHARS = 80
MAX_CALENDAR_CHARS = 40
NO_TITLE = "(no title)"
ELLIPSIS = "…"
# Control characters (Cc: newlines, tabs) become spaces. Format, private-use and
# unassigned characters (Cf, Co, Cn: bidi overrides, zero-width, soft hyphen, the
# U+E0000 tag block that can hide text) are dropped.
_SPACED_CATEGORIES = frozenset({"Cc"})
_DROPPED_CATEGORIES = frozenset({"Cf", "Co", "Cn"})
_SPACES = re.compile(r"\s+")


@dataclass(frozen=True)
class AgendaEvent:
    """One agenda row. starts_at is for sorting only and isn't written out."""

    starts_at: datetime
    start: str
    end: str | None
    is_all_day: bool
    title: str
    calendar: str

    def sort_key(self) -> tuple[datetime, bool, str]:
        """Start time, then all-day before timed on the same instant, then title."""
        return (self.starts_at, not self.is_all_day, self.title)

    def to_json(self) -> dict[str, Any]:
        """The cache/--json shape: start, end, all_day, title, calendar."""
        return {
            "start": self.start,
            "end": self.end,
            "all_day": self.is_all_day,
            "title": self.title,
            "calendar": self.calendar,
        }


def clean_text(text: object, max_chars: int) -> str:
    """One line of plain text, at most `max_chars` long (ending in … when cut)."""
    flat = _SPACES.sub(" ", "".join(_safe_char(char) for char in str(text))).strip()
    if len(flat) <= max_chars:
        return flat
    return flat[: max_chars - 1].rstrip() + ELLIPSIS


def _safe_char(char: str) -> str:
    """`char` itself, a space for a control character, or "" for an invisible one."""
    category = unicodedata.category(char)
    if category in _SPACED_CATEGORIES:
        return " "
    return "" if category in _DROPPED_CATEGORIES else char


def normalize_event(
    raw: dict[str, Any], calendar_name: str, zone: tzinfo | None
) -> AgendaEvent | None:
    """Turn a raw event into an AgendaEvent.

    Args:
        raw: An events.list item.
        calendar_name: The calendar's display name.
        zone: The zone for timed events; None means this PC's local time (DST-aware).

    Returns:
        The event, or None when it's cancelled or its start can't be read.
    """
    if raw.get("status") == "cancelled":
        return None
    start = _parse_moment(raw.get("start"), zone)
    if start is None:
        return None
    end = _parse_moment(raw.get("end"), zone)
    starts_at, start_text, is_all_day = start
    return AgendaEvent(
        starts_at=starts_at,
        start=start_text,
        end=end[1] if end else None,
        is_all_day=is_all_day,
        title=clean_text(raw.get("summary") or NO_TITLE, MAX_TITLE_CHARS) or NO_TITLE,
        calendar=clean_text(calendar_name, MAX_CALENDAR_CHARS),
    )


def _parse_moment(value: object, zone: tzinfo | None) -> tuple[datetime, str, bool] | None:
    """Read {"date": ...} or {"dateTime": ...} into (sortable instant, text, is_all_day)."""
    if not isinstance(value, dict):
        return None
    try:
        if isinstance(value.get("dateTime"), str):
            moment = datetime.fromisoformat(value["dateTime"])
            if moment.tzinfo is None:
                return None  # RFC 3339 always has an offset; a bare time is ambiguous
            local = moment.astimezone(zone)
            return local, local.isoformat(timespec="seconds"), False
        if isinstance(value.get("date"), str):
            day = date.fromisoformat(value["date"])
            return _midnight(day, zone), day.isoformat(), True
    except ValueError:
        return None
    return None


def _midnight(day: date, zone: tzinfo | None) -> datetime:
    """The start of `day` in `zone` (or local time), as an aware datetime for sorting."""
    if zone is None:
        return datetime.combine(day, time.min).astimezone()
    return datetime.combine(day, time.min, tzinfo=zone)
