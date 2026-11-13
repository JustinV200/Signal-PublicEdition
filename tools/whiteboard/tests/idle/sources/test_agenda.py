"""read_agenda: calendar events merge into UPCOMING; a missing, stale or bad cache adds none."""

import json
from datetime import date, datetime, timedelta, timezone, tzinfo
from pathlib import Path

import pytest

from whiteboard.idle import DatedItem, read_agenda, upcoming_rows

# Written as chr() so the source itself holds no invisible character.
RIGHT_TO_LEFT_OVERRIDE = chr(0x202E)
EDT = timezone(timedelta(hours=-4))
NOW = datetime(2026, 10, 20, 12, 0, tzinfo=EDT)
LAST_DAY = date(2026, 10, 27)
EVENTS = [
    {
        "start": "2026-10-20T15:00:00-04:00",
        "end": "2026-10-20T16:00:00-04:00",
        "all_day": False,
        "title": "Book club <b>Zoom</b>" + RIGHT_TO_LEFT_OVERRIDE,
        "calendar": "the owner",
    },
    {
        "start": "2026-10-20T08:00:00-04:00",
        "end": "2026-10-20T09:00:00-04:00",
        "all_day": False,
        "title": "Already over",
        "calendar": "the owner",
    },
    {
        "start": "2026-10-19",
        "end": "2026-10-22",
        "all_day": True,
        "title": "Fall break",
        "calendar": "School",
    },
    {"start": "2026-11-30", "end": None, "all_day": True, "title": "Too far", "calendar": "x"},
    {"start": 5, "title": "Malformed", "calendar": "x"},
]


def write(path: Path, updated: datetime, events: object) -> Path:
    path.write_text(json.dumps({"updated": updated.isoformat(), "events": events}), "utf-8")
    return path


def test_events_merge_with_plan_items_by_day_and_time(tmp_path: Path) -> None:
    agenda = read_agenda(write(tmp_path / "agenda.json", NOW, EVENTS), NOW, LAST_DAY)
    ml = {"label": "HIST 205", "color": "#f0f"}
    plan_item = DatedItem(date(2026, 10, 21), "08:30", ml, "Notebook 08:30")
    rows = upcoming_rows([plan_item, *agenda], NOW.date())
    assert [(row["day"], row["chip"]["label"], row["text"]) for row in rows] == [
        ("Today", "Cal", "Book club Zoom 15:00"),  # tags and the bidi override stripped
        ("Today", "Cal", "Fall break"),  # began earlier, still on: shown today, untimed last
        ("Wed", "HIST 205", "Notebook 08:30"),
    ]


@pytest.mark.parametrize(
    "contents",
    [
        None,  # no file yet
        "not json",
        json.dumps({"updated": (NOW - timedelta(hours=3)).isoformat(), "events": EVENTS}),
        json.dumps({"updated": "yesterday", "events": EVENTS}),
        json.dumps({"updated": NOW.isoformat(), "events": "nope"}),
    ],
)
def test_missing_stale_or_invalid_cache_adds_nothing(tmp_path: Path, contents: str | None) -> None:
    path = tmp_path / "agenda.json"
    if contents is not None:
        path.write_text(contents, "utf-8")
    assert read_agenda(path, NOW, LAST_DAY) == []


class NewYork2026(tzinfo):
    """America/New_York for 2026 alone: EDT until Sun 1 Nov 06:00 UTC, then EST.

    zoneinfo would need the tzdata package on Windows, so the test brings its own zone.
    """

    SWITCH_UTC = datetime(2026, 11, 1, 6, 0)

    def fromutc(self, moment: datetime) -> datetime:
        utc = moment.replace(tzinfo=None)
        offset = timedelta(hours=-4 if utc < self.SWITCH_UTC else -5)
        return (utc + offset).replace(tzinfo=self)

    def utcoffset(self, moment: datetime | None) -> timedelta:
        return timedelta(hours=-4) + self.dst(moment) - timedelta(hours=1)

    def dst(self, moment: datetime | None) -> timedelta:
        is_summer = moment is not None and moment.replace(tzinfo=None) < datetime(2026, 11, 1, 1)
        return timedelta(hours=1 if is_summer else 0)


def test_event_times_use_the_offset_on_their_own_date(tmp_path: Path) -> None:
    zone = NewYork2026()
    # Fixed-offset, as datetime.now().astimezone() gives in the daemon: today's -04:00.
    now = datetime(2026, 10, 31, 12, 0, tzinfo=EDT)
    events = [
        # After the switch to EST: 10:00 there, not 11:00 at today's -04:00.
        {
            "start": "2026-11-02T10:00:00-05:00",
            "end": "2026-11-02T10:30:00-05:00",
            "all_day": False,
            "title": "Standup",
            "calendar": "the owner",
        },
        # A timed event that began on an earlier day and is still on: today, untimed.
        {
            "start": "2026-10-30T09:00:00-04:00",
            "end": "2026-11-03T17:00:00-05:00",
            "all_day": False,
            "title": "Conference",
            "calendar": "the owner",
        },
    ]
    path = write(tmp_path / "agenda.json", now, events)
    rows = upcoming_rows(read_agenda(path, now, date(2026, 11, 7), zone), now.date())
    assert [(row["day"], row["text"]) for row in rows] == [
        ("Today", "Conference"),
        ("Mon", "Standup 10:00"),
    ]
