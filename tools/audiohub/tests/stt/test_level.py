"""Tests for audiohub.stt.level: the auto-gain applied before VAD."""

import numpy as np
import pytest

from audiohub.stt.level import MAX_GAIN, PEAK_HALF_LIFE_MS, TARGET_PEAK, LevelNormalizer

FRAME_MS = 32.0


def frame_with_peak(peak: float) -> np.ndarray:
    frame = np.zeros(512, dtype=np.float32)
    frame[100] = peak
    frame[200] = -peak / 2
    return frame


def peak_of(frame: np.ndarray) -> float:
    return float(np.max(np.abs(frame)))


@pytest.fixture
def normalizer() -> LevelNormalizer:
    return LevelNormalizer(FRAME_MS)


def test_loud_input_passes_through_unchanged(normalizer: LevelNormalizer) -> None:
    frame = frame_with_peak(0.8)
    np.testing.assert_array_equal(normalizer.apply(frame), frame)


def test_quiet_input_is_boosted_to_the_target_peak(normalizer: LevelNormalizer) -> None:
    assert peak_of(normalizer.apply(frame_with_peak(0.1))) == pytest.approx(TARGET_PEAK)


def test_gain_is_capped(normalizer: LevelNormalizer) -> None:
    assert peak_of(normalizer.apply(frame_with_peak(0.001))) == pytest.approx(0.001 * MAX_GAIN)


def test_digital_silence_stays_silent(normalizer: LevelNormalizer) -> None:
    result = normalizer.apply(np.zeros(512, dtype=np.float32))
    assert not np.any(result)


def test_loud_onset_after_quiet_is_not_clipped(normalizer: LevelNormalizer) -> None:
    for _ in range(50):
        normalizer.apply(frame_with_peak(0.001))
    assert peak_of(normalizer.apply(frame_with_peak(0.9))) == pytest.approx(0.9)


def test_gain_recovers_after_the_half_life(normalizer: LevelNormalizer) -> None:
    normalizer.apply(frame_with_peak(0.5))
    frames_per_half_life = round(PEAK_HALF_LIFE_MS / FRAME_MS)
    for _ in range(frames_per_half_life - 1):
        normalizer.apply(np.zeros(512, dtype=np.float32))
    # Tracked peak has halved to ~0.25, so a 0.05 frame gets ~2x gain.
    assert peak_of(normalizer.apply(frame_with_peak(0.05))) == pytest.approx(0.1, rel=0.05)


def test_reset_forgets_the_tracked_peak(normalizer: LevelNormalizer) -> None:
    normalizer.apply(frame_with_peak(0.9))
    normalizer.reset()
    assert peak_of(normalizer.apply(frame_with_peak(0.1))) == pytest.approx(TARGET_PEAK)


def test_output_is_a_new_float32_array(normalizer: LevelNormalizer) -> None:
    frame = frame_with_peak(0.1)
    result = normalizer.apply(frame)
    assert result is not frame
    assert result.dtype == np.float32
    assert peak_of(frame) == pytest.approx(0.1)


@pytest.mark.parametrize(
    ("frame_ms", "target_peak", "max_gain"),
    [(0, 0.5, 10), (32, 1.5, 10), (32, 0.5, 0.5)],
)
def test_invalid_arguments_raise(frame_ms: float, target_peak: float, max_gain: float) -> None:
    with pytest.raises(ValueError):
        LevelNormalizer(frame_ms, target_peak, max_gain)
