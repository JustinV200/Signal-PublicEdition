"""Tests for RemoteFrameSource: phone chunks of any size in, exact 512-sample frames out."""

import asyncio

import numpy as np
import pytest

from audiohub.phone import RemoteFrameSource
from audiohub.stt import FRAME_SAMPLES


def _pcm(samples: np.ndarray) -> bytes:
    return samples.astype("<i2").tobytes()


@pytest.mark.asyncio
async def test_chunks_of_any_size_become_exact_frames(link):
    source = RemoteFrameSource(link)
    samples = (np.arange(3000) % 400 - 200).astype("<i2")
    chunk_sizes = [1, 37, 512, 700, 1000, 750]
    assert sum(chunk_sizes) == len(samples)
    async with source:
        frames = source.frames()
        offset = 0
        for size in chunk_sizes:
            link.receive_audio(_pcm(samples[offset : offset + size]))
            offset += size
        received = [await asyncio.wait_for(anext(frames), 1) for _ in range(3000 // FRAME_SAMPLES)]
    assert all(len(frame) == FRAME_SAMPLES and frame.dtype == np.float32 for frame in received)
    expected = samples[: len(received) * FRAME_SAMPLES] / 32768
    np.testing.assert_allclose(np.concatenate(received), expected)


@pytest.mark.asyncio
async def test_pausing_tells_the_phone_and_drops_audio(link, socket, wait_until):
    await link.attach(socket)
    source = RemoteFrameSource(link)
    async with source:
        frames = source.frames()
        source.paused = True
        link.receive_audio(_pcm(np.full(1000, 1000)))
        source.paused = False
        link.receive_audio(_pcm(np.full(FRAME_SAMPLES, 2000)))
        frame = await asyncio.wait_for(anext(frames), 1)
    # Only audio from after the pause comes through, whole.
    np.testing.assert_allclose(frame, 2000 / 32768)
    mic_off, mic_on = {"type": "mic", "on": False}, {"type": "mic", "on": True}
    await wait_until(lambda: socket.sent_json == [mic_on, mic_off, mic_on])
