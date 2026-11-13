"""Tests for reading the owner's wake time."""

from datetime import datetime

import pytest

from sleepmode.schedule import parse_wake_time

EVENING = datetime(2026, 10, 19, 23, 15)
EARLY = datetime(2026, 10, 20, 5, 0)


@pytest.mark.parametrize(
    ("text", "now", "expected"),
    [
        ("07:00", EVENING, datetime(2026, 10, 20, 7, 0)),
        ("07:00", EARLY, datetime(2026, 10, 20, 7, 0)),  # after midnight: still today
        ("7:30 PM", EARLY, datetime(2026, 10, 20, 19, 30)),
        ("12am", EVENING, datetime(2026, 10, 20, 0, 0)),
        ("12 p.m.", EARLY, datetime(2026, 10, 20, 12, 0)),
        ("23:15", EVENING, datetime(2026, 10, 20, 23, 15)),  # exactly now means tomorrow
        ("2026-10-20T06:45", EVENING, datetime(2026, 10, 20, 6, 45)),
    ],
)
def test_clock_and_iso_times(text: str, now: datetime, expected: datetime) -> None:
    assert parse_wake_time(text, now) == expected


@pytest.mark.parametrize("text", ["2026-10-19T07:00", "25:00", "13pm", "noonish"])
def test_rejects_past_and_unreadable_times(text: str) -> None:
    with pytest.raises(ValueError):
        parse_wake_time(text, EVENING)
