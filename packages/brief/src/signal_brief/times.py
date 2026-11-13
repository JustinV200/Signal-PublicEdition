"""Time helpers shared by every state file: local aware times, written as ISO 8601."""

from datetime import datetime


def local_now() -> datetime:
    """Now, as an aware local time."""
    return datetime.now().astimezone()


def to_iso(moment: datetime) -> str:
    """`moment` as ISO 8601 to the second, with its UTC offset."""
    return moment.isoformat(timespec="seconds")


def from_iso(text: object) -> datetime | None:
    """An ISO 8601 time read back from a state file, or None if missing or unreadable.

    A time without an offset is taken as local, so comparisons never mix naive and
    aware times.
    """
    if not isinstance(text, str):
        return None
    try:
        moment = datetime.fromisoformat(text)
    except ValueError:
        return None
    return moment if moment.tzinfo else moment.astimezone()
