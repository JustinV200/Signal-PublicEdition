"""Re-cut variable-size audio blocks into fixed-size frames.

PortAudio delivers blocks of whatever size the driver picks, and resampling
changes those sizes again. The VAD needs exactly N samples per frame
(512 at 16 kHz for Silero), so Microphone runs its audio through a FrameChunker.
"""

import numpy as np


class FrameChunker:
    """Buffer mono samples and hand them out in frames of exactly `frame_samples`."""

    def __init__(self, frame_samples: int) -> None:
        """Create an empty chunker.

        Args:
            frame_samples: Samples per output frame.

        Raises:
            ValueError: If `frame_samples` is not positive.
        """
        if frame_samples <= 0:
            raise ValueError(f"frame_samples must be positive, got {frame_samples}")
        self._frame_samples = frame_samples
        self._pending = np.zeros(0, dtype=np.float32)

    def push(self, block: np.ndarray) -> list[np.ndarray]:
        """Add a block and return every complete frame now available, oldest first.

        Leftover samples are kept for the next call. Returned frames are float32
        and don't share memory with later pushes.
        """
        buffered = np.concatenate((self._pending, np.asarray(block, dtype=np.float32)))
        frame_count = len(buffered) // self._frame_samples
        used = frame_count * self._frame_samples
        frames = [
            buffered[start : start + self._frame_samples]
            for start in range(0, used, self._frame_samples)
        ]
        # Copy the remainder so it doesn't keep the whole `buffered` array alive.
        self._pending = buffered[used:].copy()
        return frames

    def clear(self) -> None:
        """Drop any partial frame, e.g. after a pause, so old and new audio don't mix."""
        self._pending = np.zeros(0, dtype=np.float32)
