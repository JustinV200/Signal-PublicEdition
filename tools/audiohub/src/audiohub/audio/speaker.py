"""Async playback of whole audio buffers on an output device.

`Speaker.play` resolves the device spec (indexes change when Bluetooth
reconnects), opens a mono stream at the device's native rate, resamples the
buffer to that rate, and waits until PortAudio has played it out, with a
deadline in case the device stalls. `stop()` cuts playback short. TTS output
(24 kHz from Kokoro) is the usual input.
"""

import asyncio
from collections.abc import Callable
from typing import Any

import numpy as np
import sounddevice as sd

from audiohub.audio.resample import resample
from audiohub.audio.streams import AudioStreamError, close_stream, open_mono_stream, start_stream

# Extra time allowed beyond the buffer's duration before playback counts as
# stalled. Covers stream start-up and Bluetooth buffering, plus the glasses'
# switch to the Hands-Free profile when their mic opens, which was measured
# delaying a 1 s tone by up to 1.7 s.
PLAYBACK_DEADLINE_MARGIN_S = 5.0


class _PlaybackBuffer:
    """Feeds one buffer to the PortAudio output callback (runs on the audio thread)."""

    def __init__(self) -> None:
        self._samples = np.zeros(0, dtype=np.float32)
        self._position = 0
        # Plain bool: written on the loop thread, read on the audio thread.
        # Assignment is atomic under the GIL, so no lock is needed.
        self._is_stop_requested = False

    def load(self, samples: np.ndarray) -> None:
        self._samples = samples
        self._position = 0

    def request_stop(self) -> None:
        self._is_stop_requested = True

    def fill(self, outdata: np.ndarray, frame_count: int, time_info: Any, status: Any) -> None:
        if self._is_stop_requested:
            outdata.fill(0)
            raise sd.CallbackAbort
        chunk = self._samples[self._position : self._position + frame_count]
        outdata[: len(chunk), 0] = chunk
        outdata[len(chunk) :] = 0
        self._position += len(chunk)
        if self._position >= len(self._samples):
            # CallbackStop lets PortAudio finish the queued buffers before stopping.
            raise sd.CallbackStop


class Speaker:
    """Plays mono audio buffers on one output device, one buffer at a time.

    Call `play` and `stop` from the asyncio loop thread.
    """

    def __init__(self, device: str | int | None = None) -> None:
        """Remember the output device; it is resolved and opened per `play` call.

        Args:
            device: Device spec (name substring, index, or None for the default).
        """
        self._device_spec = device
        self._current: tuple[_PlaybackBuffer, asyncio.Event] | None = None

    @property
    def is_playing(self) -> bool:
        """Whether a `play` call is in progress."""
        return self._current is not None

    async def play(self, samples: np.ndarray, sample_rate: int) -> None:
        """Play a mono buffer and return when it has finished (or `stop()` was called).

        Args:
            samples: Mono float audio, shape `(n,)`.
            sample_rate: The buffer's sample rate in Hz; it's resampled to the
                device's native rate.

        Raises:
            RuntimeError: If another `play` is already in progress.
            DeviceNotFoundError: If the spec matches no current output device.
            AudioStreamError: If the device can't be opened or started, or
                playback doesn't finish within its duration plus
                PLAYBACK_DEADLINE_MARGIN_S.
            ValueError: If `sample_rate` is not positive.
        """
        if self._current is not None:
            raise RuntimeError("Speaker is already playing; call stop() first")
        if len(samples) == 0:
            return
        finished = asyncio.Event()
        buffer = _PlaybackBuffer()
        stream = open_mono_stream(
            "output", self._device_spec, buffer.fill, finished_callback=_event_setter(finished)
        )
        self._current = (buffer, finished)
        try:
            device_rate = int(stream.samplerate)
            device_samples = resample(samples, sample_rate, device_rate)
            buffer.load(device_samples)
            start_stream(stream)
            await _wait_until_played(finished, len(device_samples) / device_rate)
        finally:
            self._current = None
            # Closing discards anything still queued, which is what stop() wants.
            close_stream(stream)

    def stop(self) -> None:
        """Cut the current playback short so `play` returns promptly. No-op when idle."""
        if self._current is None:
            return
        buffer, finished = self._current
        buffer.request_stop()
        finished.set()


def _event_setter(event: asyncio.Event) -> Callable[[], None]:
    """Return a PortAudio finished_callback that sets `event` on the running loop."""
    loop = asyncio.get_running_loop()

    def set_event() -> None:
        # Audio thread. Must return None: sounddevice's cffi wrapper rejects
        # any other return value (e.g. the Handle call_soon_threadsafe returns).
        loop.call_soon_threadsafe(event.set)

    return set_event


async def _wait_until_played(finished: asyncio.Event, duration_s: float) -> None:
    deadline_s = duration_s + PLAYBACK_DEADLINE_MARGIN_S
    try:
        await asyncio.wait_for(finished.wait(), timeout=deadline_s)
    except TimeoutError as error:
        raise AudioStreamError(
            f"playback of {duration_s:.1f}s of audio did not finish within {deadline_s:.1f}s; "
            "the output device may have stalled or disconnected"
        ) from error
