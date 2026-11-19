"""The list reads the tool makes: the primary calendar, the calendar list, events.

Each asks only for the fields it uses (the `fields` parameter), so descriptions,
locations and links never even reach this process. Attendees come back without
addresses (self and response only): with two or more, maxAttendees cuts the list
to the owner's own entry; with exactly one, Google returns that one, whoever it is.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from urllib.parse import quote

from calendar_tool.errors import ApiError
from calendar_tool.google_api.client import CalendarClient

# The API's own page-size maximum for events.list.
EVENTS_PAGE_SIZE = 250
CALENDAR_FIELDS = "items(id,summary,summaryOverride,selected),nextPageToken"
# id and the rest beyond status/summary/start/end are what an edit needs: which event,
# whether it repeats, whether the tool made it (the private marker), and the owner's
# own response to an invite.
EVENT_FIELDS = (
    "items(id,status,summary,start,end,recurringEventId,organizer/self,"
    "attendees(self,responseStatus),extendedProperties/private),nextPageToken"
)
# With more attendees than this, Google returns only the owner's own entry; with
# exactly this many, it returns that entry whoever's it is.
MAX_ATTENDEES = 1


@dataclass(frozen=True)
class CalendarInfo:
    """One calendar in the owner's list: its id and the name the owner sees."""

    calendar_id: str
    name: str


def primary_calendar_email(client: CalendarClient) -> str:
    """The signed-in address: the primary calendar's id is the account's email.

    Raises:
        ApiError: The entry has no address; otherwise as CalendarClient.get.
    """
    entry = client.get("users/me/calendarList/primary", {"fields": "id"})
    email = entry.get("id")
    if not isinstance(email, str) or "@" not in email:
        raise ApiError("The primary calendar had no email address.")
    return email


def list_selected_calendars(client: CalendarClient) -> list[CalendarInfo]:
    """The calendars ticked ("selected") in Google Calendar's sidebar.

    Raises:
        As CalendarClient.get_all_items.
    """
    entries = client.get_all_items("users/me/calendarList", {"fields": CALENDAR_FIELDS})
    calendars = []
    for entry in entries:
        calendar_id = entry.get("id")
        # The API only sends "selected" when it's true.
        if entry.get("selected") is not True or not isinstance(calendar_id, str):
            continue
        name = entry.get("summaryOverride") or entry.get("summary") or calendar_id
        calendars.append(CalendarInfo(calendar_id, str(name)))
    return calendars


def list_events(
    client: CalendarClient, calendar_id: str, start: datetime, end: datetime
) -> list[dict[str, Any]]:
    """Events overlapping [start, end) on one calendar, recurring ones expanded.

    Args:
        client: The API client.
        calendar_id: From list_selected_calendars.
        start, end: Timezone-aware bounds.

    Raises:
        As CalendarClient.get_all_items.
    """
    params = {
        "timeMin": start.isoformat(),
        "timeMax": end.isoformat(),
        "singleEvents": "true",
        "orderBy": "startTime",
        "maxResults": EVENTS_PAGE_SIZE,
        "maxAttendees": MAX_ATTENDEES,
        "fields": EVENT_FIELDS,
    }
    return client.get_all_items(f"calendars/{quote_id(calendar_id)}/events", params)


def quote_id(identifier: str) -> str:
    """A calendar or event id made safe for one URL path segment.

    Calendar ids hold '@' and '#', which must not rewrite the URL path.
    """
    return quote(identifier, safe="")
