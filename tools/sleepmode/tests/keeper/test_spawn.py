"""Tests for starting the keeper, with a stand-in command (no real keeper runs)."""

import sys

import pytest

import sleepmode.keeper.spawn as spawn
from sleepmode.keeper import KeeperOptions, start_keeper

OPTIONS = KeeperOptions("session", rects=(), keep_display_on=False, grace_s=5.0)


def test_a_keeper_that_dies_straight_away_is_a_failed_start(monkeypatch) -> None:
    # Sleep must never report success with no keeper holding it up.
    crash = [sys.executable, "-c", "raise SystemExit(3)"]
    monkeypatch.setattr(spawn, "keeper_command", lambda options: crash)
    with pytest.raises(OSError, match="exit code 3"):
        start_keeper(OPTIONS, startup_check_s=30)
