"""load_target: re-read the event a change will hit, right before the change, and settle its scope.

The gate and the write both act on this fresh read, never on what the model saw
earlier: the event may have been edited, deleted, or turned out to be someone
else's. An occurrence id acts on that occurrence; the whole series takes an
explicit is_series, and then the series itself is read and written.
"""

from dataclasses import dataclass
from typing import Any

from calendar_tool.changes.models import EventRef
from calendar_tool.errors import ApiError, ChangeRefused
from calendar_tool.google_api import (
    CalendarClient,
    CalendarInfo,
    EventAddress,
    calendar_entry,
    get_event,
    is_tool_event,
)

CANCELLED = "cancelled"


@dataclass(frozen=True)
class Target:
    """The event a change writes to, as it is now.

    Attributes:
        address: Its calendar, id (the series' id when is_series) and etag.
        calendar: The calendar's id and the name the owner sees.
        raw: The event as just read (EVENT_FIELDS).
        is_series: The change covers every occurrence.
    """

    address: EventAddress
    calendar: CalendarInfo
    raw: dict[str, Any]
    is_series: bool

    @property
    def is_mine(self) -> bool:
        """True when this tool created the event (its private marker is set)."""
        return is_tool_event(self.raw)


def load_target(client: CalendarClient, ref: EventRef) -> Target:
    """Read the calendar entry and the event, and resolve a series change to the series.

    Raises:
        ChangeRefused: A calendar he can't edit, an event already deleted, a series id
            without is_series, or is_series on an event that doesn't repeat.
        CalendarError: The reads failed (an unknown id is the API's 404).
    """
    entry = calendar_entry(client, ref.calendar_id)
    if not entry.is_writable:
        # No calendar name: it's third-party text, and errors reach the model unframed.
        raise ChangeRefused("You can't edit events on that calendar.")
    raw = get_event(client, EventAddress(entry.calendar_id, ref.event_id))
    raw = _scoped(client, entry.calendar_id, raw, ref.is_series)
    if raw.get("status") == CANCELLED:
        raise ChangeRefused("That event is already deleted.")
    event_id = raw.get("id")
    if not isinstance(event_id, str) or not event_id:
        raise ApiError("The Calendar API sent an event without an id.")
    etag = raw.get("etag") if isinstance(raw.get("etag"), str) else None
    address = EventAddress(entry.calendar_id, event_id, etag)
    return Target(address, CalendarInfo(entry.calendar_id, entry.name), raw, ref.is_series)


def _scoped(
    client: CalendarClient, calendar_id: str, raw: dict[str, Any], is_series: bool
) -> dict[str, Any]:
    """The event to act on: `raw` itself, or its series when is_series."""
    if not is_series:
        if raw.get("recurrence"):
            raise ChangeRefused(
                "That id is a whole repeating series. Pass series to change all of it, "
                "or use one occurrence's id from the agenda."
            )
        return raw
    series_id = raw.get("recurringEventId")
    if isinstance(series_id, str) and series_id:
        return get_event(client, EventAddress(calendar_id, series_id))
    if raw.get("recurrence"):
        return raw
    raise ChangeRefused("That event doesn't repeat, so there's no series to change.")
