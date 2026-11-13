"""Tests for WavFrameSource and read_wav_mono."""

import asyncio
import wave

import numpy as np
import pytest

from audiohub.loop import WavFrameSource
from audiohub.loop.hearing import read_wav_mono
from audiohub.stt import FRAME_SAMPLES, SAMPLE_RATE


def _write_wav(path, samples: np.ndarray, rate: int, channels: int = 1, width: int = 2) -> None:
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(channels)
        wav.setsampwidth(width)
        wav.setframerate(rate)
        wav.writeframes(samples.tobytes())


def test_reads_16_bit_stereo_as_mono_16k(tmp_path):
    # One second of stereo at 22.05 kHz: left 0.5, right -0.5 -> mono silence.
    frames = np.tile(np.array([16384, -16384], dtype="<i2"), 22050)
    _write_wav(tmp_path / "a.wav", frames, 22050, channels=2)
    samples = read_wav_mono(tmp_path / "a.wav")
    assert samples.dtype == np.float32
    assert len(samples) == pytest.approx(SAMPLE_RATE, abs=2)
    assert np.abs(samples).max() < 1e-3


def test_reads_8_bit_unsigned(tmp_path):
    _write_wav(tmp_path / "b.wav", np.full(16000, 192, dtype="u1"), 16000, width=1)
    assert read_wav_mono(tmp_path / "b.wav").mean() == pytest.approx(0.5, abs=0.01)


def test_rejects_24_bit(tmp_path):
    _write_wav(tmp_path / "c.wav", np.zeros(300, dtype="u1"), 16000, width=3)
    with pytest.raises(ValueError, match="24-bit"):
        read_wav_mono(tmp_path / "c.wav")


def test_rejects_non_wav_and_missing_files(tmp_path):
    (tmp_path / "d.wav").write_bytes(b"not a wav file at all")
    with pytest.raises(ValueError, match="not a readable WAV"):
        read_wav_mono(tmp_path / "d.wav")
    with pytest.raises(OSError):
        read_wav_mono(tmp_path / "missing.wav")


@pytest.mark.asyncio
async def test_streams_the_file_then_silence(tmp_path):
    tone = np.full(FRAME_SAMPLES + 100, 8192, dtype="<i2")
    _write_wav(tmp_path / "e.wav", tone, SAMPLE_RATE)
    source = WavFrameSource(tmp_path / "e.wav", is_realtime=False)
    assert source.duration_s == pytest.approx((FRAME_SAMPLES + 100) / SAMPLE_RATE)
    frames = []
    async with source:
        async for frame in source.frames():
            frames.append(frame)
            if len(frames) == 4:
                break
    assert all(frame.shape == (FRAME_SAMPLES,) for frame in frames)
    assert frames[0].min() == pytest.approx(0.25)
    assert frames[1][:100].min() == pytest.approx(0.25) and not frames[1][100:].any()
    assert not frames[2].any() and not frames[3].any()


@pytest.mark.asyncio
async def test_frames_that_fall_due_while_paused_are_dropped(tmp_path):
    # 3 frames (96 ms) of audio, all due while the source is paused for 300 ms.
    _write_wav(tmp_path / "f.wav", np.full(FRAME_SAMPLES * 3, 8192, dtype="<i2"), SAMPLE_RATE)
    source = WavFrameSource(tmp_path / "f.wav")
    source.paused = True
    unpause = asyncio.get_running_loop().call_later(0.3, setattr, source, "paused", False)
    async with source:
        async for frame in source.frames():
            first_frame = frame
            break
    unpause.cancel()
    assert not first_frame.any()
