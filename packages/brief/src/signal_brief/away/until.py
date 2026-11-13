"""parse_until: when away mode should end, from what the owner said.

A day without a time ("Sunday", "tomorrow", "2026-10-25") ends at 17:00 that day.
An ISO date-time is taken as given (local if it has no offset).
"""

import re
from datetime import date, datetime, time, timedelta

from signal_brief.text import ERROR_QUOTE_CHARS

# "Away until Sunday" ends at 17:00 that day.
DAY_END = time(17, 0)
WEEKDAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")
ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
WEEKDAY_ABBREVIATION_CHARS = 3


def parse_until(text: str, now: datetime) -> datetime | None:
    """The end time `text` names, or None for "" (no end: away lasts 3 days).

    Args:
        text: "", a weekday ("sunday", "sun"), "tomorrow", an ISO date or date-time.
        now: The current time (aware); a weekday means its next 17:00 after now.

    Returns:
        An aware end time after `now`, or None.

    Raises:
        ValueError: Unreadable, or not in the future.
    """
    cleaned = text.strip().lower()
    if not cleaned:
        return None
    end = _parse_day(cleaned, now)
    if end is None:
        try:
            end = datetime.fromisoformat(cleaned.upper())
        except ValueError as error:
            raise ValueError(f"can't read the end time {text[:ERROR_QUOTE_CHARS]!r}") from error
        end = end if end.tzinfo else end.astimezone()
    if end <= now:
        raise ValueError(f"the end time {text[:ERROR_QUOTE_CHARS]!r} has already passed")
    return end


def _parse_day(cleaned: str, now: datetime) -> datetime | None:
    """17:00 on the day a weekday, "tomorrow" or ISO date names, or None if it's none of them."""
    if ISO_DATE.fullmatch(cleaned):
        return _at_day_end(date.fromisoformat(cleaned))
    if cleaned == "tomorrow":
        return _at_day_end(now.date() + timedelta(days=1))
    for index, name in enumerate(WEEKDAYS):
        if cleaned in (name, name[:WEEKDAY_ABBREVIATION_CHARS]):
            day = now.date() + timedelta(days=(index - now.weekday()) % 7)
            # Said on that weekday after 17:00, it means next week's.
            if _at_day_end(day) <= now:
                day += timedelta(days=7)
            return _at_day_end(day)
    return None


def _at_day_end(day: date) -> datetime:
    # Local time on that day, so a DST change in between doesn't shift it an hour.
    return datetime.combine(day, DAY_END).astimezone()
