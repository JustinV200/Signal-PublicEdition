"""Tests for PresenceFiles: asleep or away from other tools' state files, failing open."""

from datetime import datetime, timedelta

import pytest

from audiohub.kernel.ipc.presence import ASLEEP_REASON, AWAY_REASON, PresenceFiles

NOW = datetime(2026, 10, 25, 12, 0).astimezone()
LATER = (NOW + timedelta(hours=2)).isoformat()
EARLIER = (NOW - timedelta(hours=2)).isoformat()


@pytest.mark.parametrize(
    ("sleep_text", "away_text", "expected"),
    [
        (None, None, None),  # neither tool has run: fail open
        ('{"is_asleep": true}', None, ASLEEP_REASON),
        ('{"is_asleep": false}', f'{{"on": true, "until": "{LATER}"}}', AWAY_REASON),
        (None, f'{{"on": true, "until": "{EARLIER}"}}', None),  # away mode has expired
        (None, '{"on": false}', None),
        ("{not json", "[1, 2]", None),  # unreadable files fail open
    ],
    ids=["missing", "asleep", "away", "away-expired", "away-off", "malformed"],
)
def test_quiet_reason(tmp_path, sleep_text, away_text, expected) -> None:
    files = PresenceFiles(tmp_path / "state.json", tmp_path / "away.json")
    for path, text in ((files.sleep_state, sleep_text), (files.away_state, away_text)):
        if text is not None:
            path.write_text(text, encoding="utf-8")
    assert files.quiet_reason(NOW) == expected
