"""Tests for Hearing: frames -> segmenter -> transcriber, plus pause/resume and quiet waits."""

import asyncio

import numpy as np
import pytest

from audiohub.config import VadSettings
from audiohub.loop import Hearing
from audiohub.stt import FRAME_SAMPLES, SAMPLE_RATE, UtteranceSegmenter

# Fast segmentation: 2 silent frames end an utterance, one loud frame is enough.
VAD = VadSettings(threshold=0.5, min_silence_ms=64, min_speech_ms=32, pre_roll_ms=0)
LOUD = np.full(FRAME_SAMPLES, 0.5, dtype=np.float32)
QUIET = np.zeros(FRAME_SAMPLES, dtype=np.float32)


class LoudnessVad:
    """A SpeechScorer that calls any loud frame speech."""

    threshold = 0.5

    def speech_probability(self, frame: np.ndarray) -> float:
        return 1.0 if np.abs(frame).max() > 0.1 else 0.0

    def reset(self) -> None:
        pass


class ScriptedTranscriber:
    def __init__(self, texts: list[str]) -> None:
        self.texts = list(texts)
        self.lengths: list[int] = []
        self.is_loaded = False
        self.device_in_use, self.model_in_use = "cpu", "tiny"

    def load(self) -> None:
        self.is_loaded = True

    def transcribe(self, audio: np.ndarray) -> str:
        self.lengths.append(len(audio))
        return self.texts.pop(0)


class ListSource:
    """A FrameSource that yields a fixed list of frames, then ends."""

    def __init__(self, frames: list[np.ndarray]) -> None:
        self.frames_to_send = frames
        self.paused = False
        self.is_open = False

    async def __aenter__(self) -> "ListSource":
        self.is_open = True
        return self

    async def __aexit__(self, *exc_info) -> None:
        self.is_open = False

    async def frames(self):
        for frame in self.frames_to_send:
            await asyncio.sleep(0)
            if not self.paused:
                yield frame


def _hearing(frames, texts) -> tuple[Hearing, ListSource, ScriptedTranscriber]:
    source = ListSource(frames)
    transcriber = ScriptedTranscriber(texts)
    return Hearing(source, UtteranceSegmenter(LoudnessVad(), VAD), transcriber), source, transcriber


async def _collect(hearing: Hearing) -> list:
    async with hearing:
        return [heard async for heard in hearing.utterances()]


@pytest.mark.asyncio
async def test_each_utterance_is_transcribed_with_timings():
    frames = [LOUD, LOUD, QUIET, QUIET, LOUD, QUIET, QUIET]
    hearing, _, transcriber = _hearing(frames, ["Hey Claude.", " What's up? "])
    heard = await _collect(hearing)
    assert [item.text for item in heard] == ["Hey Claude.", "What's up?"]
    assert heard[0].audio_s == pytest.approx(transcriber.lengths[0] / SAMPLE_RATE)
    assert all(item.stt_s >= 0 for item in heard)
    assert heard[0].started_at <= heard[1].started_at


@pytest.mark.asyncio
async def test_empty_transcripts_are_skipped():
    hearing, _, _ = _hearing([LOUD, QUIET, QUIET, LOUD, QUIET, QUIET], ["", "Hello."])
    assert [item.text for item in await _collect(hearing)] == ["Hello."]


@pytest.mark.asyncio
async def test_pause_drops_audio_and_resume_discards_half_utterance():
    source = ListSource([])
    segmenter = UtteranceSegmenter(LoudnessVad(), VAD)
    hearing = Hearing(source, segmenter, ScriptedTranscriber(["After the pause."]))
    segmenter.push(LOUD)  # the user was mid-word when Claude started talking
    hearing.pause()
    assert source.paused and hearing.is_paused
    hearing.resume()
    assert not source.paused
    source.frames_to_send = [LOUD, QUIET, QUIET]
    heard = await _collect(hearing)
    assert [item.text for item in heard] == ["After the pause."]
    # Only the new loud frame: the one from before the pause was discarded.
    assert heard[0].audio_s == pytest.approx(FRAME_SAMPLES / SAMPLE_RATE)


@pytest.mark.asyncio
async def test_wait_until_quiet_waits_while_user_is_mid_utterance():
    gate = asyncio.Event()

    class SlowSource(ListSource):
        async def frames(self):
            yield LOUD
            await gate.wait()
            yield QUIET
            yield QUIET

    source = SlowSource([])
    hearing = Hearing(source, UtteranceSegmenter(LoudnessVad(), VAD), ScriptedTranscriber(["x"]))
    async with hearing:
        consumer = asyncio.create_task(_drain(hearing))
        await asyncio.sleep(0.01)
        assert await hearing.wait_until_quiet(0.02) is False
        gate.set()
        assert await hearing.wait_until_quiet(1) is True
        await consumer


async def _drain(hearing: Hearing) -> None:
    async for _ in hearing.utterances():
        pass
