"""Public API of calendar_tool.google_api: the Calendar REST client, its reads and its writes."""

from calendar_tool.google_api.client import API_BASE, CalendarClient, HttpSession
from calendar_tool.google_api.event_facts import (
    MARKER_KEY,
    MARKER_VALUE,
    has_guests,
    invite_response,
    is_recurring,
    is_tool_event,
    marker_properties,
    own_attendee,
)
from calendar_tool.google_api.events import (
    CalendarEntry,
    EventAddress,
    calendar_entry,
    delete_event,
    get_event,
    insert_event,
    patch_event,
)
from calendar_tool.google_api.resources import (
    CalendarInfo,
    list_events,
    list_selected_calendars,
    primary_calendar_email,
)

__all__ = [
    "API_BASE",
    "MARKER_KEY",
    "MARKER_VALUE",
    "CalendarClient",
    "CalendarEntry",
    "CalendarInfo",
    "EventAddress",
    "HttpSession",
    "calendar_entry",
    "delete_event",
    "get_event",
    "has_guests",
    "insert_event",
    "invite_response",
    "is_recurring",
    "is_tool_event",
    "list_events",
    "list_selected_calendars",
    "marker_properties",
    "own_attendee",
    "patch_event",
    "primary_calendar_email",
]
