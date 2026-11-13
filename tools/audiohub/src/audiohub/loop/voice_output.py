"""`VoiceOutput`: speak text to the user, with music ducked while Claude talks.

The back end of the voice loop and of the `say`/`voices` commands. Each call
runs clean_for_speech -> split_sentences -> Kokoro synthesis (in an executor)
-> playback. The next chunk is synthesized while the current one plays, so
there is no gap between sentences and the first words come out quickly.

Music is ducked before the first chunk and restored afterwards, on errors and
cancellation too (Ctrl+C included), so it is never left quiet.
"""

import asyncio
import logging
from collections.abc import Awaitable, Callable, Sequence
from concurrent.futures import ThreadPoolExecutor
from typing import Protocol

import numpy as np

from audiohub.audio import AudioStreamError
from audiohub.tts import clean_for_speech, split_sentences

from .phrases import has_words

logger = logging.getLogger(__name__)

# The text spoken to load the TTS model before the first real message.
WARM_UP_TEXT = "Ready."

ChunkListener = Callable[[str], None]
"""Called with each sentence chunk just before it starts playing."""


class SpeechSynthesizer(Protocol):
    """What VoiceOutput needs from `audiohub.tts.Synthesizer`."""

    def synthesize(self, text: str, voice: str | None = None) -> tuple[np.ndarray, int]:
        """Return (samples, sample_rate) for one chunk of plain text."""
        ...


class AudioPlayer(Protocol):
    """What VoiceOutput needs from `audiohub.audio.Speaker`."""

    async def play(self, samples: np.ndarray, sample_rate: int) -> None:
        """Play one buffer and return when it ends or stop() is called."""
        ...

    def stop(self) -> None:
        """Cut the current playback short."""
        ...


class MusicDucker(Protocol):
    """What VoiceOutput needs from `audiohub.audio.Ducker` (blocking calls)."""

    def duck(self) -> None:
        """Lower the music. Never raises."""
        ...

    def restore(self) -> None:
        """Put the music back to its volume before duck(). Never raises."""
        ...


def speakable_chunks(texts: Sequence[str]) -> list[str]:
    """Clean and split messages into the sentence chunks to synthesize, in order.

    Chunks with no words (a stray "..." or "-") are left out, because Kokoro
    can't voice them.
    """
    return [
        chunk
        for text in texts
        for chunk in split_sentences(clean_for_speech(text))
        if has_words(chunk)
    ]


class VoiceOutput:
    """Speaks messages one at a time. Call from the event loop thread."""

    def __init__(
        self, synthesizer: SpeechSynthesizer, speaker: AudioPlayer, ducker: MusicDucker
    ) -> None:
        """Wire the output chain.

        Args:
            synthesizer: Text to audio (blocking; runs in the default executor).
            speaker: Plays audio on the output device.
            ducker: Lowers and restores music (blocking; runs on its own thread).
        """
        self._synthesizer = synthesizer
        self._speaker = speaker
        self._ducker = ducker
        # One thread runs duck() and restore() in submission order. A restore
        # queued after a cancelled duck() then still runs after it, never
        # beside it, so the captured volume is always put back.
        self._ducking_thread = ThreadPoolExecutor(max_workers=1, thread_name_prefix="ducking")
        # Speech and cues (the wake chime) take turns on the one output device.
        self._output_lock = asyncio.Lock()
        # Plays holding or waiting for the output, and whether the music is
        # ducked for them: speech queued behind the chime keeps its duck.
        self._ducked_plays = 0
        self._is_ducked = False
        self._is_speaking = False
        self._is_stop_requested = False

    @property
    def speaking(self) -> bool:
        """Whether a `speak` call is in progress."""
        return self._is_speaking

    async def speak(self, text: str, voice: str | None = None) -> bool:
        """Speak one message (markdown and code are cleaned out first).

        A chunk the output device fails to play (it won't open, or playback
        stalls past the Speaker's deadline) is logged and skipped, and the
        rest of the message still plays.

        Args:
            text: The message as written, e.g. a Claude reply.
            voice: A Kokoro voice name, or None for the configured voice.

        Returns:
            True if every chunk played (or `stop()` cut it short on purpose),
            False if the device failed to play at least one chunk.

        Raises:
            RuntimeError: If another speak call is still running.
            ValueError: If the voice doesn't exist.
            ModelDownloadError: If the TTS model can't be downloaded.
        """
        return await self.speak_many([text], voice)

    async def speak_many(
        self,
        texts: Sequence[str],
        voice: str | None = None,
        on_chunk: ChunkListener | None = None,
    ) -> bool:
        """Speak several messages back to back under a single duck.

        Same result and errors as `speak`. Returns early, with music restored,
        after `stop()`.

        Args:
            texts: The messages, in speaking order.
            voice: A Kokoro voice name, or None for the configured voice.
            on_chunk: Told each sentence chunk as it starts playing (barge-in
                uses it to know what Claude said when). Chunks skipped after
                `stop()` are never reported.
        """
        if self._is_speaking:
            raise RuntimeError("VoiceOutput is already speaking; call stop() first")
        chunks = speakable_chunks(texts)
        if not chunks:
            return True
        self._is_speaking = True
        self._is_stop_requested = False
        loop = asyncio.get_running_loop()

        async def play() -> bool:
            try:
                return await self._play_pipelined(loop, chunks, voice, on_chunk)
            finally:
                # Done speaking already while the music fades back in.
                self._is_speaking = False

        try:
            return await self._play_ducked(play)
        finally:
            self._is_speaking = False  # also if cancelled before playing began

    async def play_cue(self, samples: np.ndarray, sample_rate: int) -> bool:
        """Play a short non-speech sound, such as the wake chime, with music ducked.

        It never counts as speaking (`speaking` stays False, `stop()` leaves
        it alone). It waits for speech in progress to finish, and speech that
        starts meanwhile waits for it, since the output plays one buffer at a time.

        Args:
            samples: Mono float audio in [-1, 1].
            sample_rate: Its rate in Hz; the output device resamples it.

        Returns:
            True if it played, False if the device failed to play it (logged).
        """
        return await self._play_ducked(lambda: self._play_chunk(samples, sample_rate))

    def stop(self) -> None:
        """Stop speaking now: cut the current chunk and skip the rest. No-op when idle."""
        if not self._is_speaking:
            return
        self._is_stop_requested = True
        self._speaker.stop()

    def close(self) -> None:
        """Shut the ducking thread down, first letting a queued restore() finish.

        Blocks for up to about `fade_ms`. Don't speak after closing.
        """
        self._ducking_thread.shutdown(wait=True)

    async def warm_up(self) -> None:
        """Load the TTS model now (in an executor) so the first reply isn't delayed.

        Raises:
            ModelDownloadError: If the model files can't be downloaded.
        """
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._synthesizer.synthesize, WARM_UP_TEXT)

    async def _play_ducked(self, play: Callable[[], Awaitable[bool]]) -> bool:
        """Run `play` with the output to itself and the music ducked, then restore the music.

        A play already queued when the one before it ends keeps its duck, so
        the music isn't restored and ducked again back to back; the last play
        out restores it.
        """
        loop = asyncio.get_running_loop()
        self._ducked_plays += 1
        try:
            async with self._output_lock:
                if not self._is_ducked:
                    # Set first: a duck() whose await is cancelled still runs,
                    # so it must still be restored.
                    self._is_ducked = True
                    await loop.run_in_executor(self._ducking_thread, self._ducker.duck)
                return await play()
        finally:
            self._ducked_plays -= 1
            if self._ducked_plays == 0 and self._is_ducked:
                self._is_ducked = False
                # Queued before any await, so it runs even if this await is
                # cancelled again; the ducking thread finishes it regardless.
                await loop.run_in_executor(self._ducking_thread, self._ducker.restore)

    async def _play_pipelined(
        self,
        loop: asyncio.AbstractEventLoop,
        chunks: list[str],
        voice: str | None,
        on_chunk: ChunkListener | None,
    ) -> bool:
        """Play the chunks in order while synthesizing the next one in the background.

        Returns:
            False if any chunk failed to play, else True.
        """
        is_all_played = True
        upcoming = self._synthesize_later(loop, chunks[0], voice)
        try:
            for index in range(len(chunks)):
                samples, sample_rate = await upcoming
                upcoming = None
                if index + 1 < len(chunks):
                    upcoming = self._synthesize_later(loop, chunks[index + 1], voice)
                if self._is_stop_requested:
                    break
                if on_chunk is not None:
                    on_chunk(chunks[index])
                is_all_played &= await self._play_chunk(samples, sample_rate)
                if self._is_stop_requested:
                    break
        finally:
            # An abandoned synthesis still finishes on its thread; drop its result.
            if upcoming is not None:
                upcoming.cancel()
        return is_all_played

    async def _play_chunk(self, samples: np.ndarray, sample_rate: int) -> bool:
        try:
            await self._speaker.play(samples, sample_rate)
        except AudioStreamError:
            # A stalled or vanished device loses this sentence, not the whole
            # message; music is still restored when the message ends.
            logger.exception("could not play a speech chunk; skipping it")
            return False
        return True

    def _synthesize_later(
        self, loop: asyncio.AbstractEventLoop, chunk: str, voice: str | None
    ) -> asyncio.Future[tuple[np.ndarray, int]]:
        return loop.run_in_executor(None, self._synthesizer.synthesize, chunk, voice)
