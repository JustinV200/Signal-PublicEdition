"""The single-event REST calls: read one event and a calendar's entry, insert, patch, delete.

Each write passes the `sendUpdates` it is given, and patch/delete send the etag
from the read as If-Match, so an event that changed since it was read (say
while the owner's dialog was open) isn't overwritten. Nothing here builds a
body; changes/ does, and it never puts attendees in one except the owner's
own response.
"""

from dataclasses import dataclass
from typing import Any

from calendar_tool.errors import ApiError
from calendar_tool.google_api.client import CalendarClient
from calendar_tool.google_api.resources import MAX_ATTENDEES, quote_id

# Everything a change needs to decide and describe itself. A reply must name the
# owner's own address, so attendees includes email. With two or more attendees,
# maxAttendees cuts the list to the owner's own entry (Google's docs say it then
# sets attendeesOmitted, unverified live; has_guests doesn't need it, since any
# attendee entry means someone else is on the event); with exactly one, Google
# returns it whoever it is. No result, dialog or file ever shows another
# person's address: only the owner's own entry is used.
EVENT_FIELDS = (
    "id,etag,status,summary,start,end,recurringEventId,recurrence,organizer/self,"
    "attendees(email,self,responseStatus),attendeesOmitted,extendedProperties/private"
)
ENTRY_FIELDS = "id,summary,summaryOverride,accessRole"
# The calendarList access roles that may add, change and delete events.
WRITABLE_ROLES = frozenset({"owner", "writer"})
SEND_NO_UPDATES = "none"


@dataclass(frozen=True)
class CalendarEntry:
    """One calendar in the owner's list: its id, the name he sees, and if he can edit it."""

    calendar_id: str
    name: str
    is_writable: bool


@dataclass(frozen=True)
class EventAddress:
    """Where an event lives, and the etag it was read with (None: not read yet)."""

    calendar_id: str
    event_id: str
    etag: str | None = None

    def path(self) -> str:
        """The events/<id> path below calendar/v3/."""
        return f"calendars/{quote_id(self.calendar_id)}/events/{quote_id(self.event_id)}"


def calendar_entry(client: CalendarClient, calendar_id: str) -> CalendarEntry:
    """The owner's calendarList entry for `calendar_id` ("primary" works too).

    Raises:
        ApiError: It isn't in his list, or has no id; otherwise as CalendarClient.get.
    """
    entry = client.get(f"users/me/calendarList/{quote_id(calendar_id)}", {"fields": ENTRY_FIELDS})
    real_id = entry.get("id")
    if not isinstance(real_id, str) or not real_id:
        raise ApiError("The calendar list entry had no id.")
    name = entry.get("summaryOverride") or entry.get("summary") or real_id
    return CalendarEntry(real_id, str(name), entry.get("accessRole") in WRITABLE_ROLES)


def get_event(client: CalendarClient, address: EventAddress) -> dict[str, Any]:
    """The event as it is now, with EVENT_FIELDS only.

    Raises:
        As CalendarClient.get.
    """
    params = {"fields": EVENT_FIELDS, "maxAttendees": MAX_ATTENDEES}
    return client.get(address.path(), params)


def insert_event(client: CalendarClient, calendar_id: str, body: dict[str, Any]) -> dict[str, Any]:
    """Create the event and return it (EVENT_FIELDS). Nobody is notified.

    Raises:
        As CalendarClient.send.
    """
    params = {"sendUpdates": SEND_NO_UPDATES, "fields": EVENT_FIELDS}
    return client.send("POST", f"calendars/{quote_id(calendar_id)}/events", params, body)


def patch_event(
    client: CalendarClient,
    address: EventAddress,
    body: dict[str, Any],
    send_updates: str = SEND_NO_UPDATES,
) -> dict[str, Any]:
    """Patch the event (If-Match its etag) and return it (EVENT_FIELDS).

    Args:
        client: The API client.
        address: Which event, and the etag it was read with.
        body: The fields to change.
        send_updates: Google's sendUpdates: "none", or "all" for the owner's RSVP.

    Raises:
        As CalendarClient.send.
    """
    params = {"sendUpdates": send_updates, "fields": EVENT_FIELDS, "maxAttendees": MAX_ATTENDEES}
    return client.send("PATCH", address.path(), params, body, address.etag)


def delete_event(client: CalendarClient, address: EventAddress) -> None:
    """Delete the event (If-Match its etag). An occurrence's id cancels that occurrence only.

    Nobody is notified.

    Raises:
        As CalendarClient.send.
    """
    client.send("DELETE", address.path(), {"sendUpdates": SEND_NO_UPDATES}, etag=address.etag)
