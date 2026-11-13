"""`Hearing`: frames from a FrameSource -> utterance segmenter -> Whisper -> transcripts.

The front half of the voice loop. Each finished utterance is transcribed in an
executor so the event loop keeps running while Whisper works. The `listen`
command prints what comes out; the conversation routes it to the brain.
Half-duplex control lives here too (`audio.barge_in` off): `pause()` while
Claude speaks so the glasses mic doesn't hear the speaker, and `resume()`
afterwards. With barge-in on, the hub never pauses and every utterance is
transcribed, Claude talking or not.
"""

import asyncio
import logging
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass
from types import TracebackType
from typing import Self

import numpy as np

from audiohub.stt import SAMPLE_RATE, Transcriber, UtteranceSegmenter

from ..status import format_duration
from .frame_source import FrameSource

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Heard:
    """One transcribed utterance.

    Attributes:
        text: What Whisper heard (never empty).
        started_at: `time.monotonic()` when the utterance began, approximately
            (its end minus its length, pre-roll included).
        audio_s: Length of the utterance audio in seconds.
        stt_s: How long transcription took in seconds.
    """

    text: str
    started_at: float
    audio_s: float
    stt_s: float

    def describe(self) -> str:
        """The transcript and its timings for a status line.

        Returns:
            e.g. '"Hey Claude, what's the time?" (2.1 s audio, stt 85 ms)'
        """
        timing = f"{format_duration(self.audio_s)} audio, stt {format_duration(self.stt_s)}"
        return f'"{self.text}" ({timing})'


class Hearing:
    """Turns a frame source into a stream of transcripts.

    Use it as an async context manager (it opens and closes the source), then
    iterate `utterances()`. Only one consumer may iterate.
    """

    def __init__(
        self, source: FrameSource, segmenter: UtteranceSegmenter, transcriber: Transcriber
    ) -> None:
        """Wire the pipeline. Nothing opens until `async with`.

        Args:
            source: The microphone or a stand-in such as WavFrameSource.
            segmenter: Cuts frames into utterances.
            transcriber: Turns an utterance into text (synchronous, so it
                runs in an executor).
        """
        self._source = source
        self._segmenter = segmenter
        self._transcriber = transcriber
        # Set while the user isn't mid-utterance, so speech can wait for a gap.
        self._quiet = asyncio.Event()
        self._quiet.set()

    @property
    def device_in_use(self) -> str | None:
        """The Whisper device ("cuda" or "cpu") once the model is loaded."""
        return self._transcriber.device_in_use

    @property
    def model_in_use(self) -> str | None:
        """The Whisper model name once loaded (differs from the config after a fallback)."""
        return self._transcriber.model_in_use

    @property
    def is_paused(self) -> bool:
        """Whether audio is currently being dropped."""
        return self._source.paused

    async def __aenter__(self) -> Self:
        """Open the frame source.

        Raises:
            AudioStreamError: If the microphone can't be opened.
        """
        await self._source.__aenter__()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Close the frame source, which ends `utterances()`."""
        await self._source.__aexit__(exc_type, exc, traceback)

    async def load(self) -> None:
        """Load and warm up the Whisper model in an executor.

        Raises:
            RuntimeError: If neither the configured nor the fallback model loads.
        """
        await asyncio.get_running_loop().run_in_executor(None, self._transcriber.load)

    def pause(self) -> None:
        """Drop all audio until `resume()` (Claude is about to speak)."""
        self._source.paused = True
        self._quiet.set()

    def resume(self) -> None:
        """Start listening again, discarding any half-heard utterance from before the pause.

        Frames still queued from before the pause were already dropped by
        `utterances()`, so only audio from after this call is heard.
        """
        self._segmenter.reset()
        self._quiet.set()
        self._source.paused = False

    async def wait_until_quiet(self, timeout_s: float) -> bool:
        """Wait until the user isn't in the middle of an utterance.

        Args:
            timeout_s: Give up after this many seconds.

        Returns:
            True if the user is quiet, False if they were still talking at the timeout.
        """
        try:
            await asyncio.wait_for(self._quiet.wait(), timeout_s)
        except TimeoutError:
            return False
        return True

    async def utterances(self) -> AsyncIterator[Heard]:
        """Yield each non-empty transcript until the source closes.

        Raises:
            RuntimeError: If the Whisper model can't be loaded.
        """
        loop = asyncio.get_running_loop()
        async for frame in self._source.frames():
            # Frames queued before the pause took effect may still arrive;
            # they could hold Claude's first words, so drop them.
            if self._source.paused:
                continue
            utterance = self._segmenter.push(frame)
            self._update_quiet()
            if utterance is None:
                continue
            heard = await self._transcribe(loop, utterance)
            if heard.text:
                yield heard
            else:
                logger.debug("utterance of %.1f s had no words", heard.audio_s)

    async def _transcribe(self, loop: asyncio.AbstractEventLoop, utterance: np.ndarray) -> Heard:
        audio_s = len(utterance) / SAMPLE_RATE
        # TODO: stamp started_at from when the utterance's first frame was
        # captured, not from now minus its length. Frames that queued up while
        # the loop was busy make this run late, which skews the barge-in and
        # echo timing (speech_window.ECHO_TIMING_MARGIN_S papers over it). It
        # needs FrameSource.frames() to yield capture times with the frames.
        started_at = time.monotonic() - audio_s
        stt_started = time.monotonic()
        text = await loop.run_in_executor(None, self._transcriber.transcribe, utterance)
        return Heard(text.strip(), started_at, audio_s, time.monotonic() - stt_started)

    def _update_quiet(self) -> None:
        if self._segmenter.is_speaking:
            self._quiet.clear()
        else:
            self._quiet.set()
