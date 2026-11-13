"""Tests for audiohub.audio.speaker with a fake PortAudio output stream.

The fake stream pulls audio through the real callback on a worker thread and
calls the finished callback when PortAudio would.
"""

import asyncio
import threading
import time

import numpy as np
import pytest
import sounddevice as sd

from audiohub.audio import AudioStreamError, Speaker
from audiohub.audio import speaker as speaker_module

BLOCK_SAMPLES = 480


class FakeOutputStream:
    def __init__(self, callback, finished_callback, samplerate: float, block_delay_s: float):
        self.device_spec = None
        self.callback = callback
        self.finished_callback = finished_callback
        self.samplerate = samplerate
        self.block_delay_s = block_delay_s
        self.blocks: list[np.ndarray] = []
        self.is_closed = False
        # sounddevice's cffi wrapper rejects a non-None return, so record it.
        self.finished_result: object = "not called"
        self._thread = threading.Thread(target=self._pump, daemon=True)

    def start(self) -> None:
        self._thread.start()

    def close(self) -> None:
        self.is_closed = True
        self._thread.join(timeout=2)

    def played(self) -> np.ndarray:
        return np.concatenate(self.blocks)[:, 0] if self.blocks else np.zeros(0)

    def _pump(self) -> None:
        while not self.is_closed:
            outdata = np.full((BLOCK_SAMPLES, 1), np.nan, dtype=np.float32)
            try:
                self.callback(outdata, BLOCK_SAMPLES, None, None)
            except sd.CallbackStop:
                self.blocks.append(outdata)
                break
            except sd.CallbackAbort:
                break
            self.blocks.append(outdata)
            time.sleep(self.block_delay_s)
        self.finished_result = self.finished_callback()


@pytest.fixture
def make_stream(monkeypatch: pytest.MonkeyPatch):
    opened: list[FakeOutputStream] = []
    settings = {"block_delay_s": 0.0}

    def open_fake(kind, device_spec, callback, finished_callback=None):
        assert kind == "output"
        stream = FakeOutputStream(callback, finished_callback, 48000.0, settings["block_delay_s"])
        stream.device_spec = device_spec
        opened.append(stream)
        return stream

    monkeypatch.setattr(speaker_module, "open_mono_stream", open_fake)
    return opened, settings


@pytest.mark.asyncio
async def test_play_resamples_and_plays_every_sample(make_stream):
    opened, _ = make_stream
    await Speaker().play(np.full(2400, 0.5, dtype=np.float32), 24000)
    played = opened[0].played()
    # 2400 samples at 24 kHz become 4800 at 48 kHz; the last block is zero-padded.
    assert np.count_nonzero(np.abs(played) > 0.25) == pytest.approx(4800, abs=8)
    assert not np.isnan(played).any()
    assert opened[0].is_closed


@pytest.mark.asyncio
async def test_finished_callback_returns_none(make_stream):
    opened, _ = make_stream
    await Speaker().play(np.ones(480, dtype=np.float32), 48000)
    assert opened[0].finished_result is None


@pytest.mark.asyncio
async def test_stop_makes_play_return_early(make_stream):
    opened, settings = make_stream
    settings["block_delay_s"] = 0.01
    speaker = Speaker()
    ten_seconds = np.ones(240000, dtype=np.float32)
    play_task = asyncio.create_task(speaker.play(ten_seconds, 24000))
    await asyncio.sleep(0.05)
    assert speaker.is_playing
    speaker.stop()
    await asyncio.wait_for(play_task, timeout=1)
    assert not speaker.is_playing
    assert len(opened[0].played()) < 48000 * 10


@pytest.mark.asyncio
async def test_second_play_while_playing_raises(make_stream):
    _, settings = make_stream
    settings["block_delay_s"] = 0.01
    speaker = Speaker()
    play_task = asyncio.create_task(speaker.play(np.ones(48000, dtype=np.float32), 48000))
    await asyncio.sleep(0.02)
    with pytest.raises(RuntimeError, match="already playing"):
        await speaker.play(np.ones(10, dtype=np.float32), 48000)
    speaker.stop()
    await play_task


@pytest.mark.asyncio
async def test_empty_buffer_opens_no_stream(make_stream):
    opened, _ = make_stream
    await Speaker().play(np.zeros(0, dtype=np.float32), 24000)
    assert opened == []


@pytest.mark.asyncio
async def test_device_spec_is_resolved_on_every_play(make_stream):
    opened, _ = make_stream
    speaker = Speaker("BT-Glasses")
    for _ in range(2):
        await speaker.play(np.ones(480, dtype=np.float32), 48000)
    assert [stream.device_spec for stream in opened] == ["BT-Glasses", "BT-Glasses"]


@pytest.mark.asyncio
async def test_stalled_playback_raises_after_the_deadline(make_stream, monkeypatch):
    opened, settings = make_stream
    # 0.1 s of audio, but the fake device takes 0.5 s per 10 ms block.
    settings["block_delay_s"] = 0.5
    monkeypatch.setattr(speaker_module, "PLAYBACK_DEADLINE_MARGIN_S", 0.05)
    speaker = Speaker()
    with pytest.raises(AudioStreamError, match="did not finish"):
        await speaker.play(np.ones(4800, dtype=np.float32), 48000)
    assert not speaker.is_playing
    assert opened[0].is_closed
