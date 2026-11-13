"""Tests for the usage line: a reset window reads as unknown, stale agents don't count."""

import json
from datetime import datetime, timedelta

from signal_tasks import NO_USAGE, read_usage

NOW = datetime(2026, 10, 20, 12, 0).astimezone()


def test_read_usage_drops_reset_windows_and_stale_agents(tmp_path) -> None:
    path = tmp_path / "usage.json"
    fresh, stale = NOW - timedelta(minutes=5), NOW - timedelta(hours=3)
    payload = {
        "five_hour": {"used_pct": 42.0, "resets_at": (NOW - timedelta(minutes=1)).isoformat()},
        "seven_day": {"used_pct": 18.0, "resets_at": (NOW + timedelta(days=2)).isoformat()},
        "sessions": {
            "s1": {"agents": [{"seen_at": fresh.isoformat()}, {"seen_at": stale.isoformat()}]},
            "s2": {"agents": [{"seen_at": fresh.isoformat()}]},
        },
        "updated_at": fresh.isoformat(),
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    usage = read_usage(path, NOW)
    assert usage is not None and usage.five_hour is None
    assert usage.seven_day is not None and usage.seven_day.used_pct == 18.0
    assert (usage.agents, usage.updated_at) == (2, fresh)
    path.write_text("{not json", encoding="utf-8")
    assert read_usage(path, NOW) is None  # keep the last copy
    assert read_usage(tmp_path / "missing.json", NOW) == NO_USAGE
