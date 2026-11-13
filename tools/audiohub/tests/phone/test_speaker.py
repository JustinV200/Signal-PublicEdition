"""Tests for RemoteSpeaker: speech goes to the phone as PCM, and play waits for the ack."""

import asyncio
import json
import struct

import numpy as np
import pytest

from audiohub.audio import AudioStreamError
from audiohub.phone import RemoteSpeaker
from audiohub.phone import speaker as speaker_module

TTS_RATE = 24000


def _ack(chunk_id: int) -> str:
    return json.dumps({"type": "played", "id": chunk_id})


@pytest.mark.asyncio
async def test_play_sends_pcm_and_returns_on_the_phones_ack(link, socket, wait_until):
    await link.attach(socket)
    speaker = RemoteSpeaker(link)
    samples = np.array([0.0, 0.5, -0.5, 1.5], dtype=np.float32)
    playing = asyncio.create_task(speaker.play(samples, TTS_RATE))
    await wait_until(lambda: socket.sent_bytes)
    chunk_id, rate = struct.unpack_from("<II", socket.sent_bytes[0])
    pcm = np.frombuffer(socket.sent_bytes[0][8:], dtype="<i2")
    assert rate == TTS_RATE
    assert pcm.tolist() == [0, 16384, -16384, 32767]  # 1.5 is clipped
    await asyncio.sleep(0.02)
    assert not playing.done()
    link.receive_control(_ack(chunk_id))
    await asyncio.wait_for(playing, 1)


@pytest.mark.asyncio
async def test_play_fails_when_the_phone_never_acks(link, socket, monkeypatch):
    monkeypatch.setattr(speaker_module, "ACK_DEADLINE_MARGIN_S", 0.05)
    await link.attach(socket)
    with pytest.raises(AudioStreamError, match="did not finish"):
        await RemoteSpeaker(link).play(np.zeros(240, dtype=np.float32), TTS_RATE)


@pytest.mark.asyncio
async def test_play_fails_at_once_without_a_phone_or_when_it_drops(link, socket, wait_until):
    speaker = RemoteSpeaker(link)
    with pytest.raises(AudioStreamError, match="no phone"):
        await speaker.play(np.zeros(240, dtype=np.float32), TTS_RATE)
    await link.attach(socket)
    playing = asyncio.create_task(speaker.play(np.zeros(TTS_RATE, dtype=np.float32), TTS_RATE))
    await wait_until(lambda: socket.sent_bytes)
    link.detach(socket)
    with pytest.raises(AudioStreamError, match="disconnected"):
        await asyncio.wait_for(playing, 1)


@pytest.mark.asyncio
async def test_stop_ends_play_and_cuts_the_phone(link, socket, wait_until):
    await link.attach(socket)
    speaker = RemoteSpeaker(link)
    playing = asyncio.create_task(speaker.play(np.zeros(TTS_RATE, dtype=np.float32), TTS_RATE))
    await wait_until(lambda: socket.sent_bytes)
    speaker.stop()
    await asyncio.wait_for(playing, 1)
    await wait_until(lambda: {"type": "stop"} in socket.sent_json)
    assert not speaker.is_playing
