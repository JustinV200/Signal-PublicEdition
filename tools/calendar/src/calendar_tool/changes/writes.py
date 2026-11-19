"""EventChanges: create, update, delete and reply to events, each one Calendar write.

Create needs no approval: the event is new and carries the tool's marker.
Update, delete and reply re-read the event first (changes/target.py), then pass
the ChangeGate, which asks the owner unless the tool made the event. Writes
never notify guests (sendUpdates=none), except a reply (see REPLY_SEND_UPDATES).
"""

from datetime import tzinfo
from typing import Any

from calendar_tool.agenda import AgendaEvent, normalize_event
from calendar_tool.changes.bodies import create_body, edit_body, reply_body
from calendar_tool.changes.gate import ChangeGate
from calendar_tool.changes.models import EventEdit, EventRef, NewEvent, check_response
from calendar_tool.changes.target import load_target
from calendar_tool.errors import ApiError, ChangeRefused
from calendar_tool.google_api import (
    CalendarClient,
    CalendarInfo,
    calendar_entry,
    delete_event,
    insert_event,
    is_recurring,
    patch_event,
)

# A reply goes to the organizer, as clicking Yes/No in Google Calendar does. With
# "none" Google still records it on the event, but an organizer outside Google
# (an Outlook invite) only ever learns of it by that email. Google's docs say "all"
# notifies all guests; in practice only the organizer seems to be emailed (unverified).
REPLY_SEND_UPDATES = "all"


class EventChanges:
    """The four calendar writes, over one client and gate."""

    def __init__(
        self, client: CalendarClient, gate: ChangeGate, zone: tzinfo | None = None
    ) -> None:
        """Args: client: the API; gate: asks the owner; zone: for local times (None: this PC's)."""
        self._client = client
        self._gate = gate
        self._zone = zone

    def create(self, new: NewEvent) -> AgendaEvent:
        """Add an event, with no guests and no notifications, marked as the tool's own.

        Raises:
            ChangeRefused: The calendar can't be edited.
            CalendarError: Bad times, or the API call failed.
        """
        body = create_body(new, self._zone)  # bad times fail before any request
        entry = calendar_entry(self._client, new.calendar_id)
        if not entry.is_writable:
            # No calendar name: it's third-party text, and errors reach the model unframed.
            raise ChangeRefused("You can't add events to that calendar.")
        raw = insert_event(self._client, entry.calendar_id, body)
        return self._view(raw, CalendarInfo(entry.calendar_id, entry.name))

    def update(self, ref: EventRef, edit: EventEdit) -> AgendaEvent:
        """Change the title, time, location or description; never attendees.

        Raises:
            ChangeRefused: The owner didn't approve, or the event can't take it.
            CalendarError: Bad times, or an API call failed.
        """
        target = load_target(self._client, ref)
        body, changes = edit_body(target.raw, edit, self._zone)
        self._gate.check(target, changes)
        return self._view(patch_event(self._client, target.address, body), target.calendar)

    def delete(self, ref: EventRef) -> None:
        """Delete the event, the one occurrence, or (ref.is_series) the whole series.

        Raises:
            ChangeRefused: The owner didn't approve, or the event can't take it.
            CalendarError: An API call failed.
        """
        target = load_target(self._client, ref)
        if target.is_series:
            what = "delete the WHOLE repeating series"
        else:
            what = "delete this occurrence" if is_recurring(target.raw) else "delete this event"
        self._gate.check(target, [what])
        delete_event(self._client, target.address)

    def respond(self, ref: EventRef, response: str) -> AgendaEvent:
        """Answer an invitation: set only the owner's own response.

        Raises:
            ChangeRefused: The owner didn't approve, or nobody invited him.
            CalendarError: A bad response, or an API call failed.
        """
        response = check_response(response)
        target = load_target(self._client, ref)
        body = reply_body(target.raw, response)
        self._gate.check(target, [f"reply {response!r} (Google emails the organizer)"])
        raw = patch_event(self._client, target.address, body, REPLY_SEND_UPDATES)
        return self._view(raw, target.calendar)

    def _view(self, raw: dict[str, Any], calendar: CalendarInfo) -> AgendaEvent:
        """The written event as an agenda row.

        Raises:
            ApiError: Google sent back an event that can't be read.
        """
        event = normalize_event(raw, calendar, self._zone)
        if event is None:
            raise ApiError("The Calendar API sent back an event that can't be read.")
        return event
