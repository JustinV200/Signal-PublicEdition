"""Tests for save_snapshot: two captures in one clock tick never overwrite each other."""

from datetime import datetime
from pathlib import Path

import numpy as np
import pytest

from whiteboard.camera import snapshots
from whiteboard.camera.snapshots import save_snapshot

FROZEN_MOMENT = datetime(2026, 10, 19, 16, 20, 52, 781259)


class FrozenClock(datetime):
    """A clock that never ticks, like Windows' coarse clock between two quick captures."""

    @classmethod
    def now(cls, tz: object = None) -> datetime:  # type: ignore[override]
        return FROZEN_MOMENT


def test_same_clock_tick_gives_distinct_time_ordered_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(snapshots, "datetime", FrozenClock)
    image = np.zeros((4, 4, 3), np.uint8)

    first = save_snapshot(image, tmp_path, keep=5)
    second = save_snapshot(image, tmp_path, keep=5)

    assert first.exists() and second.exists()
    assert second.name > first.name
