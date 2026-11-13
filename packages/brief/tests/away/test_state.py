"""Tests for away mode: the 3-day expiry, the 17:00 day end, and asleep before away."""

import json
from datetime import timedelta

import pytest
from support import at, log, make_paths

from signal_brief import away_off, away_on, away_status, current_entries, parse_until
from signal_brief.presence import read_presence


def test_away_without_an_end_expires_after_three_days_with_a_heads_up(tmp_path) -> None:
    paths = make_paths(tmp_path)
    start = at(20, 22)
    log(paths, "new", "Before away", start)
    away_on(paths, start, None, "at the cabin")
    log(paths, "decision", "Picked port 8790", start + timedelta(hours=1))
    log(paths, "waiting", "Approve the purchase", start + timedelta(hours=2))

    away_on(paths, start + timedelta(days=1), None, "still at the cabin")  # 3 days restart
    assert away_status(paths, start + timedelta(days=3, minutes=1)).state == "away"
    after = start + timedelta(days=4, minutes=1)
    assert away_status(paths, after).state == "here"
    assert away_status(paths, after).state == "here"  # ended once, logged once

    titles = [entry.content.title for entry in current_entries(paths)]
    assert titles.count("Away mode ended after 3 days, 2 items held") == 1
    due = read_presence(paths).due
    assert due is not None and (due.reason, due.marked_at) == ("away_end", after)

    # Away again and left to expire, then set over the not-yet-ended record: that one
    # ends properly first (its own heads_up), and the new one runs 3 days from now.
    away_on(paths, after, None)
    later = after + timedelta(days=3, minutes=1)
    assert away_on(paths, later, None).ends_at == later + timedelta(days=3)
    ended = [t for t in (e.content.title for e in current_entries(paths)) if "ended" in t]
    assert len(ended) == 2 and read_presence(paths).due.marked_at == later


def test_away_until_a_day_ends_at_17_and_sleepmode_reads_as_asleep(tmp_path) -> None:
    paths = make_paths(tmp_path)
    tuesday_morning = at(20, 9)
    assert parse_until("sunday", tuesday_morning) == at(25, 17)
    assert parse_until("Tue", at(20, 18)) == at(27, 17)  # after 17:00, next week's
    assert parse_until("2026-10-22", tuesday_morning) == at(22, 17)
    with pytest.raises(ValueError):
        parse_until("2026-10-19T10:00", tuesday_morning)

    away_on(paths, tuesday_morning, parse_until("sunday", tuesday_morning))
    paths.sleep_state.write_text(json.dumps({"is_asleep": True}))
    assert away_status(paths, at(21, 2)).state == "asleep"
    paths.sleep_state.write_text(json.dumps({"is_asleep": False}))
    status = away_status(paths, at(21, 9))
    assert (status.state, status.ends_at) == ("away", at(25, 17))
    assert away_on(paths, at(21, 9), None, "cabin").ends_at == at(25, 17)  # given end kept

    assert away_off(paths, at(21, 10)) == 0
    assert away_status(paths, at(21, 10)).state == "here"
    assert read_presence(paths).due.reason == "away_end"
    assert away_off(paths, at(21, 11)) is None
