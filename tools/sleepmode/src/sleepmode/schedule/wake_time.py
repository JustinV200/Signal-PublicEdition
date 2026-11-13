"""parse_wake_time: turn "07:00", "7am" or an ISO date-time into the next local wake time."""

import re
from datetime import datetime, timedelta

# "7", "07:00", "7:30", "7am", "7:30 p.m." (case-insensitive).
_CLOCK_TIME = re.compile(r"^\s*(\d{1,2})(?::(\d{2}))?\s*(?:([ap])\.?\s*m\.?)?\s*$", re.IGNORECASE)
_HOURS_PER_HALF_DAY = 12


def parse_wake_time(text: str, now: datetime) -> datetime:
    """Parse a wake time into a naive local datetime that's after `now`.

    A clock time ("07:00", "7am") means its next occurrence: today if it's still
    ahead, else tomorrow. An ISO date-time ("2026-10-20T07:00", with or without a
    UTC offset) is taken as given and must be in the future.

    Args:
        text: The owner's wake time.
        now: The current local time (naive).

    Returns:
        The wake time, naive local, with seconds dropped for clock times.

    Raises:
        ValueError: The text isn't a time this understands, or it's in the past.
    """
    clock = _CLOCK_TIME.match(text)
    if clock:
        hour, minute = _clock_hour_minute(clock)
        wake = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        return wake if wake > now else wake + timedelta(days=1)
    try:
        wake = datetime.fromisoformat(text.strip())
    except ValueError as error:
        raise ValueError(
            f"can't read the wake time {text!r}; use a time like 07:00 or 7am, "
            "or an ISO date-time like 2026-10-20T07:00"
        ) from error
    if wake.tzinfo is not None:
        wake = wake.astimezone().replace(tzinfo=None)
    if wake <= now:
        raise ValueError(f"the wake time {wake:%Y-%m-%d %H:%M} has already passed")
    return wake


def _clock_hour_minute(clock: re.Match[str]) -> tuple[int, int]:
    """Hour (0-23) and minute from a _CLOCK_TIME match, with am/pm applied."""
    hour, minute = int(clock[1]), int(clock[2] or 0)
    half = (clock[3] or "").lower()
    if minute > 59:
        raise ValueError(f"minute {minute} is out of range")
    if half:
        if not 1 <= hour <= _HOURS_PER_HALF_DAY:
            raise ValueError(f"{hour}{half}m isn't a valid 12-hour time")
        # 12am is midnight and 12pm is noon.
        hour %= _HOURS_PER_HALF_DAY
        if half == "p":
            hour += _HOURS_PER_HALF_DAY
    elif hour > 23:
        raise ValueError(f"hour {hour} is out of range")
    return hour, minute
