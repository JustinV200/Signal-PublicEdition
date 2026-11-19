"""Tests for CalendarActions' writes: request shapes, the owner's gate, and the cache refresh.

Everything runs over the fake calendar in support/calendar_data.py; no request reaches Google.
"""

from pathlib import Path

import pytest
from signal_confirm.dialog import MAX_MESSAGE_CHARS
from support.calendar_data import EVENTS_PATH, OWNER, calendar_routes, event, make_actions
from support.fakes import FakeOwner, FakeSession

from calendar_tool.changes import EventEdit, EventRef, NewEvent
from calendar_tool.changes.gate import MAX_DIALOG_CHARS
from calendar_tool.errors import ChangeRefused
from calendar_tool.service import CalendarActions

MARKER = {"private": {"signal": "1"}}
NEW_TIMES = {
    "start": {
        "dateTime": "2026-11-20T11:00:00-05:00",
        "date": None,
        "timeZone": "America/New_York",
    },
    "end": {"dateTime": "2026-11-20T12:00:00-05:00", "date": None, "timeZone": "America/New_York"},
}
REPLY = {"attendees": [{"email": OWNER, "responseStatus": "declined"}], "attendeesOmitted": True}
# Shown in full on its own line, beside hosted1's 208-character old title.
NEW_TITLE = "Quarterly planning review with the whole team, agenda to follow by email"
PHISHING_LINK = "https://phish.example/login"
# The link sits far past where the dialog used to cut new text, so it shows only in full.
NEW_DESCRIPTION = "x" * 300 + f" Join at {PHISHING_LINK}"
# Too long for the dialog to show in full.
OVERLONG_DESCRIPTION = "y" * 2000
# What the dialog must show for an operation, beyond the event's title and calendar.
# theirs1's own entry alone, with no attendeesOmitted, still counts as guests.
MUST_SHOW = {"retitle": (f"'{NEW_TITLE}'", f"'{NEW_DESCRIPTION}'", "Guests:")}


def run(actions: CalendarActions, operation: str, ref: EventRef) -> None:
    """One write by name: a time move, new text (fitting or too long), a delete or a reply."""
    if operation == "update":
        actions.update(ref, EventEdit(start="2026-11-20T11:00"))
    elif operation == "retitle":
        actions.update(ref, EventEdit(title=NEW_TITLE, description=NEW_DESCRIPTION))
    elif operation == "overlong":
        actions.update(ref, EventEdit(description=OVERLONG_DESCRIPTION))
    elif operation == "delete":
        actions.delete(ref)
    else:
        actions.respond(ref, "declined")


@pytest.mark.parametrize(
    ("start", "end", "want_start", "want_end"),
    [
        (
            "2026-11-20T15:00",
            "2026-11-20T16:30",
            {"dateTime": "2026-11-20T15:00:00-05:00"},
            {"dateTime": "2026-11-20T16:30:00-05:00"},
        ),
        ("2026-11-20", "", {"date": "2026-11-20"}, {"date": "2026-11-21"}),
    ],
)
def test_create_marks_the_event_adds_no_guests_notifies_nobody_and_refreshes_the_board(
    tmp_path: Path, start: str, end: str, want_start: dict, want_end: dict
) -> None:
    session, owner = FakeSession(calendar_routes(created=event("mine1"))), FakeOwner(False)

    result = make_actions(session, owner, tmp_path).create(
        NewEvent("Dentist", start, end, location="Main St")
    )

    [post] = session.writes()
    assert (post.method, post.path, post.params["sendUpdates"]) == ("POST", EVENTS_PATH, "none")
    # Exactly these keys: no attendees, ever.
    assert post.body == {
        "summary": "Dentist",
        "start": want_start,
        "end": want_end,
        "location": "Main St",
        "extendedProperties": MARKER,
    }
    assert owner.questions == []  # creating never asks
    assert result.event is not None and result.event.is_mine and result.is_board_refreshed
    assert (tmp_path / "agenda.json").is_file()


# Security boundary: (operation, event, series, gate on, owner clicks Allow) -> (asked, written).
@pytest.mark.parametrize(
    ("operation", "event_id", "is_series", "is_gate_on", "is_allowed", "is_asked", "is_written"),
    [
        ("update", "mine1", False, True, False, False, True),  # the tool's own: never asks
        ("delete", "mine1", False, True, False, False, True),
        ("update", "theirs1", False, True, True, True, True),
        ("update", "theirs1", False, True, False, True, False),  # Deny: nothing sent
        ("delete", "theirs1", False, True, False, True, False),
        ("respond", "theirs1", False, True, False, True, False),
        ("delete", "theirs1", False, False, False, False, True),  # gate turned off
        ("delete", "ser1_20261120", True, False, False, True, False),  # series asks anyway
        ("update", "ser1_20261120", True, False, True, True, True),
        ("delete", "ser1", False, True, True, False, False),  # a series id needs series
        ("delete", "ser1", False, False, True, False, False),
        ("delete", "ser1_20261121", True, True, False, True, False),  # the series' marker counts
        ("retitle", "hosted1", False, True, False, True, False),  # new text and guests shown
        ("retitle", "theirs1", False, True, True, True, True),  # new text shown in full
        ("overlong", "theirs1", False, True, True, False, False),  # can't show it all: refused
    ],
)
def test_the_owner_is_asked_before_any_change_to_an_event_the_tool_did_not_make(
    tmp_path: Path,
    operation: str,
    event_id: str,
    is_series: bool,
    is_gate_on: bool,
    is_allowed: bool,
    is_asked: bool,
    is_written: bool,
) -> None:
    session, owner = FakeSession(calendar_routes()), FakeOwner(is_allowed)
    actions = make_actions(session, owner, tmp_path, is_gate_on)
    ref = EventRef("primary", event_id, is_series)

    if is_written:
        run(actions, operation, ref)
    else:
        with pytest.raises(ChangeRefused):
            run(actions, operation, ref)

    assert len(owner.questions) == int(is_asked)
    assert bool(session.writes()) is is_written
    if is_asked:
        question = owner.questions[0]
        assert event(event_id)["summary"][:20] in question and "Calendar: Me" in question
        assert ("EVERY occurrence" in question) is is_series
        assert all(text in question for text in MUST_SHOW.get(operation, ()))
    if not is_written:
        assert not (tmp_path / "agenda.json").exists()
    if operation == "overlong":
        # The gate's copy of the dialog's limit: larger, and the dialog would hide text again.
        assert MAX_DIALOG_CHARS <= MAX_MESSAGE_CHARS


@pytest.mark.parametrize(
    ("operation", "event_id", "is_series", "written_id", "send_updates", "body"),
    [
        ("update", "ser1_20261120", False, "ser1_20261120", "none", NEW_TIMES),
        ("update", "ser1_20261120", True, "ser1", "none", NEW_TIMES),
        ("delete", "ser1_20261120", False, "ser1_20261120", "none", None),
        ("delete", "ser1_20261120", True, "ser1", "none", None),
        ("respond", "theirs1", False, "theirs1", "all", REPLY),
    ],
)
def test_writes_hit_the_occurrence_unless_series_and_send_only_what_changes(
    tmp_path: Path,
    operation: str,
    event_id: str,
    is_series: bool,
    written_id: str,
    send_updates: str,
    body: dict | None,
) -> None:
    session = FakeSession(calendar_routes())

    run(
        make_actions(session, FakeOwner(True), tmp_path),
        operation,
        EventRef("primary", event_id, is_series),
    )

    [write] = session.writes()
    assert write.path == f"{EVENTS_PATH}/{written_id}"
    assert write.params["sendUpdates"] == send_updates
    assert write.body == body  # a new start alone kept the hour-long length
    # If-Match the etag just re-read, so a change made meanwhile isn't overwritten.
    assert write.headers == {"If-Match": f'"etag-{written_id}"'}
