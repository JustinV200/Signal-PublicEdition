"""usage.json agents: only fresh ones count, and a bad rewrite keeps the last good copy."""

import json
import os
from datetime import datetime, timedelta

from signal_console.turns import UsageAgents

NOW = datetime.fromisoformat("2026-10-20T12:00:00-04:00")


def test_counts_fresh_agents_and_keeps_the_last_good_copy(tmp_path):
    path = tmp_path / "usage.json"
    agents = [
        {"id": "a", "seen_at": (NOW - timedelta(minutes=5)).isoformat()},
        {"id": "b", "seen_at": (NOW - timedelta(hours=3)).isoformat()},  # killed silently
    ]
    session = {"agents": agents, "updated_at": NOW.isoformat()}
    path.write_text(json.dumps({"sessions": {"s1": session}}), encoding="utf-8")
    usage = UsageAgents(path)

    assert usage.read("s1", NOW.timestamp()).count == 1
    assert usage.read("other", NOW.timestamp()).count == 0

    path.write_text("{half a file", encoding="utf-8")
    os.utime(path, ns=(0, path.stat().st_mtime_ns + 1))  # a new mtime, even on a coarse clock
    assert usage.read("s1", NOW.timestamp()).count == 1
