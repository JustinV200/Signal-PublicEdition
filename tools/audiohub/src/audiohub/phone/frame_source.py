"""`RemoteFrameSource`: the phone's mic as a FrameSource for the voice loop.

It stands where `audiohub.audio.Microphone` stands in `audiohub run`. The page
sends 16 kHz int16 chunks of whatever size it likes; PhoneLink decodes them
and this source re-cuts them into the exact 512-sample float32 frames the VAD
needs. Setting `paused` (the loop's half-duplex while Claude speaks, with
`audio.barge_in` off) also tells the page to stop sending, so Claude's voice
isn't streamed back. With barge-in on it is never set, and the page keeps
streaming while Claude talks.
"""

import asyncio
import logging
from collections.abc import AsyncIterator
from types import TracebackType
from typing import Self

import numpy as np

from audiohub.audio import FrameChunker
from audiohub.stt import FRAME_SAMPLES

from .link import PhoneLink

logger = logging.getLogger(__name__)

# Frames buffered for a slow consumer before new ones are dropped, as for the
# local mic (1000 x 512 samples at 16 kHz is about 32 seconds of audio).
MAX_QUEUED_FRAMES = 1000


class RemoteFrameSource:
    """A FrameSource fed by the phone over a PhoneLink. Only one consumer may iterate."""

    def __init__(self, link: PhoneLink) -> None:
        """Register as the link's audio sink. Frames flow only while the source is open.

        Args:
            link: The phone connection the mic audio arrives on.
        """
        self._link = link
        self._chunker = FrameChunker(FRAME_SAMPLES)
        self._queue: asyncio.Queue[np.ndarray | None] = asyncio.Queue(MAX_QUEUED_FRAMES)
        self._paused = False
        self._is_open = False
        self._has_warned_overflow = False
        link.set_audio_sink(self.push)

    @property
    def paused(self) -> bool:
        """Whether mic audio is being dropped (here and, once told, on the phone)."""
        return self._paused

    @paused.setter
    def paused(self, value: bool) -> None:
        if value == self._paused:
            return
        if value:
            # Half a frame from before the pause must not join audio from after it.
            self._chunker.clear()
        self._paused = value
        self._link.set_mic(not value)

    async def __aenter__(self) -> Self:
        """Start accepting audio from the phone."""
        self._is_open = True
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Stop accepting audio and end any `frames()` iteration."""
        self._is_open = False
        if self._queue.full():
            self._queue.get_nowait()  # make room for the end marker
        self._queue.put_nowait(None)

    async def frames(self) -> AsyncIterator[np.ndarray]:
        """Yield float32 frames of exactly FRAME_SAMPLES at 16 kHz until closed."""
        while (frame := await self._queue.get()) is not None:
            yield frame

    def push(self, samples: np.ndarray) -> None:
        """Accept one decoded mic chunk of any length (PhoneLink calls this).

        Dropped while closed or paused, like audio from a muted mic.
        """
        if not self._is_open or self._paused:
            return
        for frame in self._chunker.push(samples):
            self._enqueue(frame)

    def _enqueue(self, frame: np.ndarray) -> None:
        try:
            self._queue.put_nowait(frame)
        except asyncio.QueueFull:
            if not self._has_warned_overflow:
                logger.warning("phone mic consumer is falling behind; dropping frames")
                self._has_warned_overflow = True
