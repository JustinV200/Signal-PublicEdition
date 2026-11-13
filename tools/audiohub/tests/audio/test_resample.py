"""Tests for audiohub.audio.resample: one-shot and streaming sample-rate conversion."""

import numpy as np
import pytest

from audiohub.audio import StreamResampler, resample


def sine(frequency_hz: float, rate: int, seconds: float) -> np.ndarray:
    times = np.arange(int(rate * seconds)) / rate
    return np.sin(2 * np.pi * frequency_hz * times).astype(np.float32)


def peak_frequency(samples: np.ndarray, rate: int) -> float:
    spectrum = np.abs(np.fft.rfft(samples))
    return float(np.fft.rfftfreq(len(samples), 1 / rate)[np.argmax(spectrum)])


@pytest.mark.parametrize(("from_rate", "to_rate"), [(48000, 16000), (24000, 48000)])
def test_length_scales_with_rate(from_rate, to_rate):
    output = resample(np.zeros(from_rate, dtype=np.float32), from_rate, to_rate)
    assert len(output) == to_rate
    assert output.dtype == np.float32


def test_tone_keeps_its_pitch():
    output = resample(sine(440, 24000, 1.0), 24000, 48000)
    assert peak_frequency(output, 48000) == pytest.approx(440, abs=2)


def test_equal_rates_pass_through_without_copy():
    samples = np.ones(10, dtype=np.float32)
    assert resample(samples, 16000, 16000) is samples


def test_stereo_keeps_channels():
    assert resample(np.zeros((4800, 2), dtype=np.float32), 48000, 16000).shape == (1600, 2)


def test_empty_input_gives_empty_output():
    assert len(resample(np.zeros(0, dtype=np.float32), 48000, 16000)) == 0


def test_non_positive_rate_raises():
    with pytest.raises(ValueError, match="positive"):
        resample(np.zeros(10, dtype=np.float32), 0, 16000)


def test_stream_resampler_output_approaches_expected_length():
    resampler = StreamResampler(48000, 16000)
    produced = sum(len(resampler.process(np.zeros(480, dtype=np.float32))) for _ in range(100))
    # One second in, minus the filter delay held back inside soxr.
    assert 15000 < produced <= 16000


def test_stream_resampler_keeps_pitch_across_blocks():
    resampler = StreamResampler(48000, 16000)
    tone = sine(1000, 48000, 1.0)
    blocks = [resampler.process(tone[start : start + 441]) for start in range(0, len(tone), 441)]
    assert peak_frequency(np.concatenate(blocks), 16000) == pytest.approx(1000, abs=2)
