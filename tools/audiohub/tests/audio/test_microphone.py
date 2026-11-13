"""Tests for audiohub.audio.microphone with a fake PortAudio input stream.

The fake stream's callback is driven from a worker thread, as PortAudio does,
so the call_soon_threadsafe hand-off to asyncio is exercised for real.
"""

import asyncio

import numpy as np
import pytest
import sounddevice as sd

from audiohub.audio import AudioStreamError, Microphone
from audiohub.audio import microphone as microphone_module

BLOCK_SAMPLES = 480


class FakeInputStream:
    # Tests monkeypatch this to make start() fail.
    start_error: Exception | None = None

    def __init__(self, callback, samplerate: float, device_spec) -> None:
        self.callback = callback
        self.samplerate = samplerate
        self.device_spec = device_spec
        self.is_started = False
        self.is_closed = False

    def start(self) -> None:
        if self.start_error is not None:
            raise self.start_error
        self.is_started = True

    def close(self) -> None:
        self.is_closed = True

    def feed(self, block_count: int, value: float = 0.0) -> None:
        for _ in range(block_count):
            indata = np.full((BLOCK_SAMPLES, 1), value, dtype=np.float32)
            self.callback(indata, BLOCK_SAMPLES, None, None)


@pytest.fixture
def streams(monkeypatch: pytest.MonkeyPatch) -> list[FakeInputStream]:
    opened: list[FakeInputStream] = []

    def open_fake(kind, device_spec, callback, finished_callback=None):
        assert kind == "input"
        stream = FakeInputStream(callback, samplerate=48000.0, device_spec=device_spec)
        opened.append(stream)
        return stream

    monkeypatch.setattr(microphone_module, "open_mono_stream", open_fake)
    return opened


async def collect(mic: Microphone) -> list[np.ndarray]:
    return [frame async for frame in mic.frames()]


@pytest.mark.asyncio
async def test_frames_are_exact_size_at_the_native_rate(streams):
    mic = Microphone(frame_samples=512, target_rate=48000)
    async with mic:
        # 32 blocks x 480 = 15360 samples = exactly 30 frames of 512.
        await asyncio.to_thread(streams[0].feed, 32)
    frames = await collect(mic)
    assert len(frames) == 30
    assert all(frame.shape == (512,) and frame.dtype == np.float32 for frame in frames)


@pytest.mark.asyncio
async def test_frames_are_resampled_to_the_target_rate(streams):
    mic = Microphone(frame_samples=512, target_rate=16000)
    async with mic:
        await asyncio.to_thread(streams[0].feed, 100)  # one second at 48 kHz
    frames = await collect(mic)
    # About 16000 samples / 512 = 31 frames, minus soxr's filter delay.
    assert 29 <= len(frames) <= 31


@pytest.mark.asyncio
async def test_paused_microphone_drops_audio(streams):
    mic = Microphone(frame_samples=480, target_rate=48000)
    async with mic:
        await asyncio.to_thread(streams[0].feed, 2, 1.0)
        mic.paused = True
        await asyncio.to_thread(streams[0].feed, 5, 2.0)
        mic.paused = False
        await asyncio.to_thread(streams[0].feed, 1, 3.0)
    assert [frame[0] for frame in await collect(mic)] == [1.0, 1.0, 3.0]


@pytest.mark.asyncio
async def test_exit_closes_the_stream_and_ends_iteration(streams):
    mic = Microphone()
    async with mic:
        assert streams[0].is_started
    assert streams[0].is_closed
    assert await collect(mic) == []


@pytest.mark.asyncio
async def test_failed_start_closes_the_stream_and_raises(streams, monkeypatch):
    monkeypatch.setattr(FakeInputStream, "start_error", sd.PortAudioError("Device unavailable"))
    with pytest.raises(AudioStreamError, match="Device unavailable"):
        async with Microphone():
            pytest.fail("the body must not run")
    assert streams[0].is_closed
