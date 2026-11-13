"""Tests for audiohub.stt.vad, run against the real bundled Silero model.

Silero is small and CPU-only, so these run in milliseconds. Speech detection on
real recordings is checked by hand (`audiohub listen`), since the repo holds no
speech fixtures.
"""

import numpy as np
import pytest

from audiohub.config import VadSettings
from audiohub.stt import FRAME_SAMPLES, UtteranceSegmenter, VoiceActivityDetector
from audiohub.stt.frames import FRAME_MS
from audiohub.stt.level import LevelNormalizer


class SpyNormalizer(LevelNormalizer):
    def __init__(self) -> None:
        super().__init__(FRAME_MS)
        self.applied = 0
        self.resets = 0

    def apply(self, frame: np.ndarray) -> np.ndarray:
        self.applied += 1
        return super().apply(frame)

    def reset(self) -> None:
        self.resets += 1
        super().reset()


def quiet_noise(seed: int = 0) -> np.ndarray:
    return (np.random.default_rng(seed).standard_normal(FRAME_SAMPLES) * 0.002).astype(np.float32)


def test_quiet_noise_scores_low_even_after_gain() -> None:
    vad = VoiceActivityDetector(0.5)
    probabilities = [vad.speech_probability(quiet_noise(seed)) for seed in range(30)]
    assert max(probabilities) < 0.5


def test_silence_scores_low() -> None:
    vad = VoiceActivityDetector(0.5)
    probabilities = [vad.speech_probability(np.zeros(FRAME_SAMPLES, np.float32)) for _ in range(10)]
    assert max(probabilities) < 0.2


@pytest.mark.parametrize("threshold", [-0.1, 1.1])
def test_threshold_out_of_range_raises(threshold: float) -> None:
    with pytest.raises(ValueError, match="threshold"):
        VoiceActivityDetector(threshold)


def test_frames_go_through_the_normalizer() -> None:
    normalizer = SpyNormalizer()
    vad = VoiceActivityDetector(0.5, normalizer)
    vad.speech_probability(quiet_noise())
    assert normalizer.applied == 1


def test_reset_also_resets_the_normalizer() -> None:
    normalizer = SpyNormalizer()
    vad = VoiceActivityDetector(0.5, normalizer)
    vad.speech_probability(quiet_noise())
    vad.reset()
    assert normalizer.resets == 1


def test_real_vad_with_segmenter_ignores_background_noise() -> None:
    segmenter = UtteranceSegmenter(VoiceActivityDetector(0.5), VadSettings())
    results = [segmenter.push(quiet_noise(seed)) for seed in range(100)]
    assert all(result is None for result in results)
