"""Tests for merging the status line's rate_limits into the stored usage windows."""

from datetime import timedelta

from usage.rate_limits import merge_rate_limits
from usage.times import local_now, to_iso


def _sent(used_pct, resets_at):
    return {"used_percentage": used_pct, "resets_at": resets_at.timestamp()}


def test_missing_window_keeps_known_value_until_it_resets():
    now = local_now().replace(microsecond=0)
    known = {
        "five_hour": {"used_pct": 42.0, "resets_at": to_iso(now + timedelta(hours=2))},
        "seven_day": {"used_pct": 18.0, "resets_at": to_iso(now - timedelta(seconds=1))},
    }
    # This session sends neither window: five_hour is kept, the expired seven_day is dropped.
    merged = merge_rate_limits(known, {}, now)
    assert merged["five_hour"] == {**known["five_hour"], "changed_at": to_iso(now)}
    assert merged["seven_day"] is None
    # No rate_limits at all (not a subscriber, or before the first response) behaves the same.
    assert merge_rate_limits(known, None, now)["five_hour"] == merged["five_hour"]


def test_stale_session_cannot_lower_usage_and_a_new_window_replaces_it():
    now = local_now().replace(microsecond=0)
    resets = now + timedelta(hours=2)
    state = merge_rate_limits({}, {"five_hour": _sent(42, resets)}, now)
    # An idle session re-sends its older, lower value for the same window: ignored.
    state = merge_rate_limits(state, {"five_hour": _sent(30, resets)}, now)
    assert state["five_hour"]["used_pct"] == 42.0
    # A later reset time is a newer window, even with a lower percentage.
    next_resets = resets + timedelta(hours=5)
    state = merge_rate_limits(state, {"five_hour": _sent(3, next_resets)}, now)
    assert state["five_hour"] == {
        "used_pct": 3.0,
        "resets_at": to_iso(next_resets),
        "changed_at": to_iso(now),
    }
