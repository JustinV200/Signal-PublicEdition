"""`WavFrameSource`: plays a WAV file into the voice loop as if it came from the mic.

Used by `audiohub run --input-wav FILE` and `audiohub listen --input-wav FILE`
to test the whole pipeline without the glasses, and by tests. The file is
converted to mono 16 kHz once, then streamed in 512-sample frames paced in
real time. After the file ends the source keeps yielding silence, so the
segmenter sees the utterance end and the hub keeps running like a quiet mic.
"""

import asyncio
import time
import wave
from collections.abc import AsyncIterator
from pathlib import Path
from types import TracebackType
from typing import Self

import numpy as np

from audiohub.audio import resample
from audiohub.stt import FRAME_SAMPLES, SAMPLE_RATE

# PCM sample width in bytes -> (numpy dtype, value that maps to full scale).
# 8-bit WAV is unsigned with a 128 midpoint; wider widths are signed.
_PCM_FORMATS: dict[int, tuple[str, float]] = {
    1: ("u1", 128.0),
    2: ("<i2", 32768.0),
    4: ("<i4", 2**31),
}


def read_wav_mono(path: Path, target_rate: int = SAMPLE_RATE) -> np.ndarray:
    """Read a PCM WAV file as float32 mono samples at `target_rate`.

    Args:
        path: An 8-, 16- or 32-bit PCM WAV file; stereo is mixed down.
        target_rate: Output sample rate in Hz.

    Returns:
        float32 samples in [-1, 1].

    Raises:
        OSError: If the file can't be opened.
        ValueError: If it isn't a PCM WAV file audiohub can read.
    """
    try:
        with wave.open(str(path), "rb") as wav:
            width, channels, rate = wav.getsampwidth(), wav.getnchannels(), wav.getframerate()
            raw = wav.readframes(wav.getnframes())
    except (wave.Error, EOFError) as error:
        raise ValueError(f"{path} is not a readable WAV file: {error}") from error
    if width not in _PCM_FORMATS:
        raise ValueError(f"{path} uses {width * 8}-bit samples; use 8-, 16- or 32-bit PCM")
    dtype, full_scale = _PCM_FORMATS[width]
    samples = np.frombuffer(raw, dtype=dtype).astype(np.float32)
    if width == 1:
        samples -= full_scale
    mono = (samples / full_scale).reshape(-1, channels).mean(axis=1)
    return resample(mono.astype(np.float32), rate, target_rate)


class WavFrameSource:
    """A `FrameSource` that streams a WAV file, then silence, until closed.

    Like the mic, frames that fall due while `paused` is True are dropped.
    """

    def __init__(self, path: Path, *, is_realtime: bool = True) -> None:
        """Load the file now, so a bad path fails before the hub starts.

        Args:
            path: The WAV file (see `read_wav_mono` for supported formats).
            is_realtime: Pace frames at the speed of real audio. Tests turn
                this off to stream as fast as the consumer reads.

        Raises:
            OSError: If the file can't be opened.
            ValueError: If it isn't a readable PCM WAV file.
        """
        self.paused = False
        self._samples = read_wav_mono(path)
        self._is_realtime = is_realtime
        self._is_open = False

    @property
    def duration_s(self) -> float:
        """Length of the file's audio in seconds (the silence after it not counted)."""
        return len(self._samples) / SAMPLE_RATE

    async def __aenter__(self) -> Self:
        """Start streaming from the beginning of the file."""
        self._is_open = True
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Stop streaming; `frames()` ends at its next frame."""
        self._is_open = False

    async def frames(self) -> AsyncIterator[np.ndarray]:
        """Yield the file in FRAME_SAMPLES frames, then silent frames, until closed."""
        frame_s = FRAME_SAMPLES / SAMPLE_RATE
        # Pace against an absolute schedule so sleep overshoot doesn't add up.
        next_due = time.monotonic()
        position = 0
        while self._is_open:
            frame = self._frame_at(position)
            position += FRAME_SAMPLES
            next_due += frame_s
            delay_s = max(0.0, next_due - time.monotonic()) if self._is_realtime else 0.0
            await asyncio.sleep(delay_s)
            if self._is_open and not self.paused:
                yield frame

    def _frame_at(self, position: int) -> np.ndarray:
        frame = np.zeros(FRAME_SAMPLES, dtype=np.float32)
        chunk = self._samples[position : position + FRAME_SAMPLES]
        frame[: len(chunk)] = chunk
        return frame
