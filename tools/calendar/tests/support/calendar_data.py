"""A fake calendar for the write tests: the owner's primary calendar with four kinds of event.

- mine1: a single event this tool created (it has the private marker).
- theirs1: a single event someone else invited the owner to.
- ser1: someone else's repeating series, and ser1_20261120: one occurrence of it.
- ser1_20261121: another occurrence, carrying the marker its series doesn't.
- hosted1: an event the owner organises, with guests Google cut from the list, and a long title.
Every event answers GET, PATCH (echoing the event) and DELETE (204).
"""

from datetime import timedelta, timezone
from pathlib import Path
from typing import Any

from calendar_tool.changes import ChangeGate
from calendar_tool.google_api import CalendarClient
from calendar_tool.service import Backend, CalendarActions
from support.fakes import FakeOwner, FakeResponse, FakeSession

# A fixed zone keeps the tests independent of the PC's own.
EASTERN = timezone(timedelta(hours=-5))
OWNER = "owner@example.com"
EVENTS_PATH = "calendars/owner%40example.com/events"
INVITED = {
    "organizer": {},
    "attendees": [{"email": OWNER, "self": True, "responseStatus": "needsAction"}],
}
TIMES = {
    "start": {"dateTime": "2026-11-20T09:00:00-05:00", "timeZone": "America/New_York"},
    "end": {"dateTime": "2026-11-20T10:00:00-05:00", "timeZone": "America/New_York"},
}
MARKED = {"extendedProperties": {"private": {"signal": "1"}}}
HOSTED = {
    "organizer": {"self": True},
    "attendees": [{"email": OWNER, "self": True, "responseStatus": "accepted"}],
    "attendeesOmitted": True,
}
EVENTS: dict[str, dict[str, Any]] = {
    "mine1": {"summary": "Gym", **MARKED},
    "theirs1": {"summary": "Team sync", **INVITED},
    "ser1": {"summary": "Standup", "recurrence": ["RRULE:FREQ=DAILY"], **INVITED},
    "ser1_20261120": {"summary": "Standup", "recurringEventId": "ser1", **INVITED},
    "ser1_20261121": {"summary": "Standup", "recurringEventId": "ser1", **INVITED, **MARKED},
    "hosted1": {"summary": "Offsite " + "A" * 200, **HOSTED},
}


def event(event_id: str) -> dict[str, Any]:
    """The full raw event for an id in EVENTS."""
    return (
        {"id": event_id, "etag": f'"etag-{event_id}"', "status": "confirmed"}
        | TIMES
        | EVENTS[event_id]
    )


def calendar_routes(created: dict[str, Any] | None = None) -> dict[Any, Any]:
    """Routes for the calendar entry, the agenda list, each event, and events.insert."""
    routes: dict[Any, Any] = {
        "users/me/calendarList/primary": {"id": OWNER, "summary": "Me", "accessRole": "owner"},
        "users/me/calendarList": {"items": [{"id": OWNER, "summary": "Me", "selected": True}]},
        EVENTS_PATH: {"items": [event(event_id) for event_id in EVENTS]},
        ("POST", EVENTS_PATH): created or {},
    }
    for event_id in EVENTS:
        path = f"{EVENTS_PATH}/{event_id}"
        routes[path] = routes[("PATCH", path)] = event(event_id)
        routes[("DELETE", path)] = FakeResponse(204)
    return routes


def make_actions(
    session: FakeSession, owner: FakeOwner, tmp_path: Path, is_gate_on: bool = True
) -> CalendarActions:
    """CalendarActions over the fake session and dialog, with the cache under tmp_path."""
    backend = Backend(
        build_client=lambda: CalendarClient(session),
        build_gate=lambda: ChangeGate(is_gate_on, owner, EASTERN),
        cache_path=tmp_path / "agenda.json",
        status_path=tmp_path / "sync_status.json",
        zone=EASTERN,
    )
    return CalendarActions(backend)
