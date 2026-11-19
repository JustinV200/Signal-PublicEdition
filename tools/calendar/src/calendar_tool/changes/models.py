"""The inputs of a calendar change: a new event, an edit, which event, and RSVP answers.

Each validates itself on creation, so the CLI and the MCP server share one set
of checks at the trust boundary (the model's or the owner's arguments).
"""

from dataclasses import dataclass

from calendar_tool.errors import CalendarError

PRIMARY_CALENDAR = "primary"
MAX_TITLE_CHARS = 300
MAX_LOCATION_CHARS = 500
MAX_DESCRIPTION_CHARS = 8000
MAX_ID_CHARS = 1024
# The answers to an invitation Google takes from a guest.
RESPONSES = ("accepted", "declined", "tentative")


def _check_text(name: str, value: str | None, max_chars: int) -> None:
    """Raise CalendarError when a text argument is too long."""
    if value is not None and len(value) > max_chars:
        raise CalendarError(f"{name} is longer than {max_chars} characters.")


def _check_id(name: str, value: str) -> None:
    """Raise CalendarError for an empty or oversized calendar or event id."""
    if not value.strip() or len(value) > MAX_ID_CHARS:
        raise CalendarError(f"The {name} must be 1-{MAX_ID_CHARS} characters.")


def _check_title(title: str | None) -> None:
    """A title, when given, must have text and fit."""
    if title is not None and not title.strip():
        raise CalendarError("The title can't be empty.")
    _check_text("The title", title, MAX_TITLE_CHARS)


@dataclass(frozen=True)
class NewEvent:
    """An event to create. start/end are ISO dates or local date-times (see changes/times.py).

    An empty `end` means one day for an all-day event; a timed event needs one.
    """

    title: str
    start: str
    end: str = ""
    calendar_id: str = PRIMARY_CALENDAR
    location: str = ""
    description: str = ""

    def __post_init__(self) -> None:
        """Raises CalendarError for an empty title or text that's too long."""
        _check_title(self.title)
        _check_text("The location", self.location, MAX_LOCATION_CHARS)
        _check_text("The description", self.description, MAX_DESCRIPTION_CHARS)
        _check_id("calendar id", self.calendar_id)


@dataclass(frozen=True)
class EventEdit:
    """What to change; None leaves a field as it is, "" clears location or description."""

    title: str | None = None
    start: str | None = None
    end: str | None = None
    location: str | None = None
    description: str | None = None

    def __post_init__(self) -> None:
        """Raises CalendarError when nothing would change, or for bad text."""
        if all(value is None for value in vars(self).values()):
            raise CalendarError(
                "Nothing to change: give a new title, time, location or description."
            )
        _check_title(self.title)
        _check_text("The location", self.location, MAX_LOCATION_CHARS)
        _check_text("The description", self.description, MAX_DESCRIPTION_CHARS)


@dataclass(frozen=True)
class EventRef:
    """Which event: an id from the agenda on a calendar, and whether to act on its whole series."""

    calendar_id: str
    event_id: str
    is_series: bool = False

    def __post_init__(self) -> None:
        """Raises CalendarError for an empty or oversized id."""
        _check_id("calendar id", self.calendar_id)
        _check_id("event id", self.event_id)


def check_response(response: str) -> str:
    """The RSVP answer, checked.

    Raises:
        CalendarError: It isn't one of RESPONSES.
    """
    if response not in RESPONSES:
        raise CalendarError(f"The response must be one of: {', '.join(RESPONSES)}.")
    return response
