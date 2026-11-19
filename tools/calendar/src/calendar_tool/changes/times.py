"""Event times: the tool's start/end text to Google's {"date"} or {"dateTime"}, and back to words.

Input is `YYYY-MM-DD` for an all-day event, or an ISO date-time. A date-time
without an offset is the owner's local time (or the given zone), so
"2026-11-20T15:00" means 3 pm on this PC's clock, DST included. An all-day end
is exclusive, like Google's and the agenda's: a one-day event on the 20th ends
on the 21st.
"""

import re
from datetime import date, datetime, timedelta, tzinfo
from typing import Any

from calendar_tool.errors import ApiError, CalendarError

ONE_DAY = timedelta(days=1)
_DATE_ONLY = re.compile(r"^\d{4}-\d{2}-\d{2}$")
# Google value -> one of these; mixing them in one event is an error.
Moment = date | datetime


def parse_when(text: str, zone: tzinfo | None) -> dict[str, str]:
    """{"date": ...} for YYYY-MM-DD, else {"dateTime": ...} with an offset.

    Raises:
        CalendarError: Neither form.
    """
    text = text.strip()
    try:
        if _DATE_ONLY.match(text):
            return {"date": date.fromisoformat(text).isoformat()}
        moment = datetime.fromisoformat(text)
    except ValueError:
        raise CalendarError(
            f"Can't read the time {text!r}: use YYYY-MM-DD or YYYY-MM-DDTHH:MM."
        ) from None
    if moment.tzinfo is None:
        # astimezone() on a naive time reads it as this PC's local time.
        moment = moment.replace(tzinfo=zone) if zone else moment.astimezone()
    return {"dateTime": moment.isoformat(timespec="seconds")}


def read_moment(value: object) -> Moment:
    """The date (all-day) or aware datetime in a Google start/end value.

    Raises:
        ApiError: The value isn't a readable {"date"} or {"dateTime"}.
    """
    try:
        if isinstance(value, dict) and isinstance(value.get("dateTime"), str):
            moment = datetime.fromisoformat(value["dateTime"])
            if moment.tzinfo is not None:
                return moment
        if isinstance(value, dict) and isinstance(value.get("date"), str):
            return date.fromisoformat(value["date"])
    except ValueError:
        pass  # falls through to the error below
    raise ApiError("The event's time can't be read.")


def new_span(start: str, end: str, zone: tzinfo | None) -> tuple[dict[str, str], dict[str, str]]:
    """Start and end values for a new event; an empty end means one day when all-day.

    Raises:
        CalendarError: Unreadable times, a timed event with no end, or an end not after the start.
    """
    start_value = parse_when(start, zone)
    if end.strip():
        end_value = parse_when(end, zone)
    elif "date" in start_value:
        end_value = {"date": (date.fromisoformat(start_value["date"]) + ONE_DAY).isoformat()}
    else:
        raise CalendarError("A timed event needs an end time.")
    check_order(start_value, end_value)
    return start_value, end_value


def edited_span(
    old: tuple[dict[str, Any], dict[str, Any] | None],
    start: str | None,
    end: str | None,
    zone: tzinfo | None,
) -> tuple[dict[str, str], dict[str, str]]:
    """New start and end for an edit. A new start alone keeps the event's length.

    Args:
        old: The event's current (start, end) Google values.
        start, end: The new times as text; None keeps that side (at least one is given).
        zone: The zone for times without an offset; None means this PC's.

    Raises:
        CalendarError: Unreadable times, switching all-day/timed with only one side, a bad order.
    """
    old_start, old_end = old
    if start is not None and end is not None:
        return new_span(start, end, zone)
    if start is not None:
        start_value = parse_when(start, zone)
        end_value = _keep_length(old_start, old_end, start_value)
    else:
        start_value = _bare(old_start)
        end_value = parse_when(end or "", zone)
    check_order(start_value, end_value)
    return start_value, end_value


def check_order(start: dict[str, str], end: dict[str, str]) -> None:
    """Raise CalendarError unless both are the same kind and the end is after the start."""
    first, last = read_moment(start), read_moment(end)
    if isinstance(first, datetime) != isinstance(last, datetime):
        raise CalendarError("The start and end must both be dates or both be date-times.")
    if last <= first:
        raise CalendarError("The end must be after the start.")


def describe_span(start: object, end: object, zone: tzinfo | None) -> str:
    """The span in words for the owner's dialog, e.g. "Tue 21 Oct 2026, 09:00 to 10:00".

    Raises:
        ApiError: The start can't be read (an unreadable end is left out).
    """
    first = read_moment(start)
    try:
        last: Moment | None = read_moment(end) if end else None
    except ApiError:
        last = None
    if isinstance(first, datetime):
        first = first.astimezone(zone)
        if not isinstance(last, datetime):
            return f"{first:%a %d %b %Y, %H:%M}"
        last = last.astimezone(zone)
        pattern = "%H:%M" if last.date() == first.date() else "%a %d %b %Y, %H:%M"
        return f"{first:%a %d %b %Y, %H:%M} to {last.strftime(pattern)}"
    # An all-day end is exclusive: the last day shown is the one before it.
    if isinstance(last, date) and not isinstance(last, datetime) and last - ONE_DAY > first:
        return f"{first:%a %d %b %Y} to {last - ONE_DAY:%a %d %b %Y}, all day"
    return f"{first:%a %d %b %Y}, all day"


def _keep_length(
    old_start: dict[str, Any], old_end: dict[str, Any] | None, new_start: dict[str, str]
) -> dict[str, str]:
    """The end that keeps the event's length from new_start (same kind only)."""
    first = read_moment(old_start)
    last = read_moment(old_end) if old_end else None
    moved = read_moment(new_start)
    if last is None or isinstance(first, datetime) != isinstance(moved, datetime):
        raise CalendarError("Give an end too (switching between all-day and timed needs both).")
    if isinstance(moved, datetime):
        return {"dateTime": (moved + (last - first)).isoformat(timespec="seconds")}
    return {"date": (moved + (last - first)).isoformat()}


def _bare(value: dict[str, Any]) -> dict[str, str]:
    """Only the date or dateTime of a Google value (dropping timeZone)."""
    key = "dateTime" if isinstance(value.get("dateTime"), str) else "date"
    return {key: str(value.get(key, ""))}
