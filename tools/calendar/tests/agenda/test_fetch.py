"""Tests for fetch_agenda and sync_cache: normalising events and the cache file."""

import json
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

import pytest
from support.fakes import FakeSession

from calendar_tool.agenda import fetch_agenda, sync_cache
from calendar_tool.errors import ApiError
from calendar_tool.google_api import CalendarClient

# A fixed zone keeps the tests independent of the PC's own (no tzdata needed on Windows).
EASTERN = timezone(timedelta(hours=-4))
NOW = datetime(2026, 10, 20, 12, 0, tzinfo=EASTERN)
CALENDARS = {
    "items": [
        {"id": "owner@example.com", "summary": "the owner", "selected": True},
        {
            "id": "x#holiday@group.v.calendar.google.com",
            "summaryOverride": "Holidays",
            "summary": "Holidays in United States",
            "selected": True,
        },
        {"id": "hidden@group.calendar.google.com", "summary": "Hidden"},  # not selected
    ]
}
PRIMARY_EVENTS = [
    # Two pages, so pagination is exercised.
    {
        "items": [
            {
                "status": "confirmed",
                "summary": "CHEM 120\nlec\U000e0041ture\u202e\u00ad",
                "start": {"dateTime": "2026-10-21T13:00:00Z"},
                "end": {"dateTime": "2026-10-21T14:00:00Z"},
                "description": "never cached",
                "attendees": [{"email": "a@b.c"}],
            },
            {
                "status": "cancelled",
                "summary": "Dropped",
                "start": {"dateTime": "2026-10-21T08:00:00-04:00"},
            },
        ]
    },
    {
        "items": [
            {"summary": "x" * 200, "start": {"dateTime": "2026-10-21T06:30:00-07:00"}},
            {"start": {"date": "2026-10-21"}, "end": {"date": "2026-10-22"}},
        ]
    },
]
HOLIDAY_EVENTS = {
    "items": [
        {"summary": "Halloween", "start": {"date": "2026-10-31"}, "end": {"date": "2026-11-01"}}
    ]
}


def make_client(
    holiday_events: object = HOLIDAY_EVENTS, primary_events: object = PRIMARY_EVENTS
) -> CalendarClient:
    """None for either events argument leaves its route out, so FakeSession answers 404."""
    return CalendarClient(
        FakeSession(
            {
                "users/me/calendarList": CALENDARS,
                "calendars/owner%40example.com/events": primary_events,
                "calendars/x%23holiday%40group.v.calendar.google.com/events": holiday_events,
            }
        )
    )


def test_events_are_normalised_sorted_and_stripped_to_five_fields() -> None:
    events = [event.to_json() for event in fetch_agenda(make_client(), NOW, zone=EASTERN)[0]]

    assert events == [
        {
            "start": "2026-10-21",
            "end": "2026-10-22",
            "all_day": True,
            "title": "(no title)",
            "calendar": "the owner",
        },
        {
            "start": "2026-10-21T09:00:00-04:00",
            "end": "2026-10-21T10:00:00-04:00",
            "all_day": False,
            "title": "CHEM 120 lecture",
            "calendar": "the owner",
        },
        {
            "start": "2026-10-21T09:30:00-04:00",
            "end": None,
            "all_day": False,
            "title": "x" * 79 + "…",
            "calendar": "the owner",
        },
        {
            "start": "2026-10-31",
            "end": "2026-11-01",
            "all_day": True,
            "title": "Halloween",
            "calendar": "Holidays",
        },
    ]


def test_sync_cache_replaces_the_file_with_the_exact_shape(tmp_path: Path) -> None:
    cache = tmp_path / "state" / "agenda.json"
    cache.parent.mkdir()
    cache.write_text('{"old": true}', encoding="utf-8")

    count, _ = sync_cache(make_client(), cache, NOW.astimezone(UTC), zone=EASTERN)

    data = json.loads(cache.read_text(encoding="utf-8"))
    assert count == 4 and set(data) == {"updated", "events", "skipped"}
    assert data["updated"] == "2026-10-20T12:00:00-04:00"
    assert [e["title"] for e in data["events"]][-1] == "Halloween"
    assert all(set(e) == {"start", "end", "all_day", "title", "calendar"} for e in data["events"])
    assert [p.name for p in cache.parent.iterdir()] == ["agenda.json"]  # no temp file left


def test_one_unreadable_calendar_is_skipped_not_the_whole_sync(tmp_path: Path) -> None:
    cache = tmp_path / "agenda.json"

    count, skipped = sync_cache(make_client(holiday_events=None), cache, NOW, zone=EASTERN)

    data = json.loads(cache.read_text(encoding="utf-8"))
    assert count == 3 and skipped == data["skipped"] == ["Holidays"]
    assert {e["calendar"] for e in data["events"]} == {"the owner"}

    # Every calendar failing is systemic, not one bad calendar: raise and keep the old cache.
    with pytest.raises(ApiError):
        sync_cache(make_client(None, None), cache, NOW, zone=EASTERN)
    assert json.loads(cache.read_text(encoding="utf-8")) == data
