"""Timestamps for the state file: ISO 8601 local time with its UTC offset.

The status line sends reset times as Unix epoch seconds; the state file stores
every time as ISO text so the whiteboard and `usage show` can read it as is.
"""

from datetime import UTC, datetime


def local_now() -> datetime:
    """The current local time, timezone-aware."""
    return datetime.now().astimezone()


def to_iso(moment: datetime) -> str:
    """`moment` as ISO 8601 text to the second, e.g. 2026-10-20T14:05:00-04:00."""
    return moment.isoformat(timespec="seconds")


def parse_iso(value: object) -> datetime | None:
    """An aware datetime from stored ISO text, or None if `value` isn't one.

    Naive times are rejected: comparing them with aware ones raises TypeError.
    """
    if not isinstance(value, str):
        return None
    try:
        moment = datetime.fromisoformat(value)
    except ValueError:
        return None
    return moment if moment.tzinfo is not None else None


def from_epoch(value: object) -> datetime | None:
    """Local aware datetime from Unix epoch seconds, or None if `value` isn't a usable number."""
    # bool is an int subclass; True isn't a timestamp.
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    try:
        return datetime.fromtimestamp(value, tz=UTC).astimezone()
    except (OverflowError, OSError, ValueError):  # inf, nan, out of the platform's range
        return None
