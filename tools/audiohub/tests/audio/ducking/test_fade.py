"""Tests for audiohub.audio.ducking.fade: linear multi-session volume fades."""

import pytest

from audiohub.audio.ducking import fade as fade_module
from audiohub.audio.ducking.fade import FADE_STEP_MS, fade_volumes


class RecordingVolume:
    def __init__(self) -> None:
        self.history: list[float] = []

    def SetMasterVolume(self, level: float, event_context: object) -> None:  # noqa: N802
        self.history.append(level)


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    monkeypatch.setattr(fade_module.time, "sleep", lambda seconds: None)


def test_sessions_fade_together_in_steps_and_land_exactly_on_the_end():
    down, up = RecordingVolume(), RecordingVolume()
    # 0.1 -> 0.8 is a step size that doesn't sum to the end exactly in floats.
    fade_volumes([(down, 1.0, 0.15), (up, 0.1, 0.8)], fade_ms=50)
    assert len(down.history) == len(up.history) == 50 // FADE_STEP_MS
    assert down.history == sorted(down.history, reverse=True)
    assert down.history[-1] == 0.15
    assert up.history[-1] == 0.8


def test_zero_fade_sets_the_end_level_at_once():
    volume = RecordingVolume()
    fade_volumes([(volume, 1.0, 0.25)], fade_ms=0)
    assert volume.history == [0.25]
