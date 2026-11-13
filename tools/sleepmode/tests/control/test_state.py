"""Tests for the state file the keeper relies on."""

from datetime import datetime
from pathlib import Path

import pytest

from sleepmode.control import SleepState, StateFileError, load_state, save_state
from sleepmode.screens import NIGHT_SKY, MonitorResult


def test_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "state.json"
    projector = MonitorResult(
        "\\\\.\\DISPLAY1", "PROJ-1", NIGHT_SKY, "", (1920, 0, 1920, 1080), is_projector=True
    )
    state = SleepState(
        True,
        "abc",
        datetime(2026, 10, 19, 23, 0),
        datetime(2026, 10, 20, 7, 0),
        True,
        (projector,),
        4242,
        notes=("a note",),
    )
    save_state(path, state)
    assert load_state(path) == state
    assert list(tmp_path.iterdir()) == [path]  # no temp file left behind


def test_missing_is_none_and_malformed_raises(tmp_path: Path) -> None:
    path = tmp_path / "state.json"
    assert load_state(path) is None
    path.write_text('{"is_asleep": "yes"}', encoding="utf-8")
    with pytest.raises(StateFileError):
        load_state(path)
