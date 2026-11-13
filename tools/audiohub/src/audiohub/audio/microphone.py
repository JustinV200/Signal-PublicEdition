"""Live microphone input as an async stream of fixed-size 16 kHz mono frames.

PortAudio calls `_on_audio` on its own audio thread. That callback only copies
the block and hands it to the asyncio loop with `call_soon_threadsafe`.
Resampling and framing happen on the loop thread, and the frames go into an
asyncio.Queue that `frames()` drains. The STT segmenter is the usual consumer.
"""

import asyncio
import logging
from collections.abc import AsyncIterator
from types import TracebackType
from typing import Any

import numpy as np
import sounddevice as sd

from audiohub.audio.framing import FrameChunker
from audiohub.audio.resample import StreamResampler
from audiohub.audio.streams import close_stream, open_mono_stream, start_stream

logger = logging.getLogger(__name__)

# Frames buffered for a slow consumer before new ones are dropped
# (1000 x 512 samples at 16 kHz is about 32 seconds of audio).
MAX_QUEUED_FRAMES = 1000


class Microphone:
    """Async context manager that streams mono float32 frames from an input device.

    Usage:
        async with Microphone("BT-Glasses") as mic:
            async for frame in mic.frames():
                ...

    Set `paused = True` to drop incoming audio (e.g. while Claude speaks).
    Only one consumer may iterate `frames()`.
    """

    def __init__(
        self, device: str | int | None = None, frame_samples: int = 512, target_rate: int = 16000
    ) -> None:
        """Prepare the microphone; the device is resolved and opened on `async with`.

        Args:
            device: Device spec (name substring, index, or None for the default).
            frame_samples: Exact samples per yielded frame.
            target_rate: Sample rate of the yielded frames in Hz.

        Raises:
            ValueError: If `frame_samples` or `target_rate` is not positive.
        """
        if target_rate <= 0:
            raise ValueError(f"target_rate must be positive, got {target_rate}")
        self._device_spec = device
        self._target_rate = target_rate
        self._chunker = FrameChunker(frame_samples)
        self._queue: asyncio.Queue[np.ndarray | None] = asyncio.Queue(MAX_QUEUED_FRAMES)
        self._loop: asyncio.AbstractEventLoop | None = None
        self._stream: sd.InputStream | None = None
        self._resampler: StreamResampler | None = None
        self._native_rate = 0
        self._paused = False
        self._has_warned_overflow = False

    @property
    def paused(self) -> bool:
        """Whether incoming audio is currently being dropped."""
        return self._paused

    @paused.setter
    def paused(self, value: bool) -> None:
        # Starting a pause discards half-built frames and resampler state so
        # audio from before and after the pause never ends up in one frame.
        # Before the stream opens there is no native rate and nothing to reset.
        if value and not self._paused and self._native_rate:
            self._chunker.clear()
            self._resampler = StreamResampler(self._native_rate, self._target_rate)
        self._paused = value

    async def __aenter__(self) -> "Microphone":
        """Resolve the device spec now (indexes change on reconnect), open and start it.

        Raises:
            DeviceNotFoundError: If the spec matches no current input device.
            AudioStreamError: If the device can't be opened or started. A stream
                that fails to start is closed, not leaked.
        """
        self._loop = asyncio.get_running_loop()
        stream = open_mono_stream("input", self._device_spec, self._on_audio)
        self._native_rate = int(stream.samplerate)
        self._resampler = StreamResampler(self._native_rate, self._target_rate)
        start_stream(stream)
        self._stream = stream
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Stop the stream and end any `frames()` iteration."""
        if self._stream is not None:
            close_stream(self._stream)
            self._stream = None
        self._end_frames()

    async def frames(self) -> AsyncIterator[np.ndarray]:
        """Yield float32 mono frames of exactly `frame_samples` at `target_rate`.

        Iteration ends when the context manager exits.
        """
        while True:
            frame = await self._queue.get()
            if frame is None:
                return
            yield frame

    def _on_audio(self, indata: np.ndarray, frame_count: int, time_info: Any, status: Any) -> None:
        # PortAudio audio thread: keep this minimal. indata is reused by
        # PortAudio after we return, so copy it before handing it over.
        block = indata[:, 0].copy()
        status_text = str(status) if status else ""
        try:
            self._loop.call_soon_threadsafe(self._accept_block, block, status_text)
        except RuntimeError as error:
            # The loop has closed, so nobody can receive audio: stop the stream.
            raise sd.CallbackAbort from error

    def _accept_block(self, block: np.ndarray, status_text: str) -> None:
        # asyncio loop thread.
        if status_text:
            logger.warning("microphone stream status: %s", status_text)
        if self._paused or self._resampler is None:
            return
        for frame in self._chunker.push(self._resampler.process(block)):
            self._enqueue(frame)

    def _enqueue(self, frame: np.ndarray) -> None:
        try:
            self._queue.put_nowait(frame)
        except asyncio.QueueFull:
            if not self._has_warned_overflow:
                logger.warning("microphone consumer is falling behind; dropping frames")
                self._has_warned_overflow = True

    def _end_frames(self) -> None:
        # Make room for the end-of-stream marker if the queue is full.
        if self._queue.full():
            self._queue.get_nowait()
        self._queue.put_nowait(None)
