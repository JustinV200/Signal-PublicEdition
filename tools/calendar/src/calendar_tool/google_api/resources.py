"""The three Calendar API reads the tool makes: the primary calendar, the calendar list, events.

Each asks only for the fields it uses (the `fields` parameter), so descriptions,
attendees, locations and links never even reach this process.
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
EVENT_FIELDS = "items(status,summary,start,end),nextPageToken"


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
        "fields": EVENT_FIELDS,
    }
    # Calendar ids hold '@' and '#', which must not rewrite the URL path.
    return client.get_all_items(f"calendars/{quote(calendar_id, safe='')}/events", params)
