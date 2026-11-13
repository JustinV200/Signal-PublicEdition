"""Sample-rate conversion with soxr.

Devices are opened at their native rate (often 44.1/48 kHz, or 8/16 kHz for a
Bluetooth Hands-Free endpoint). `resample` converts whole buffers, for
example TTS output before playback. `StreamResampler` converts a live stream
block by block, keeping filter state across blocks so block edges don't click.
"""

import numpy as np
import soxr

# soxr "HQ" is its recommended quality/speed balance for speech and music.
SOXR_QUALITY = "HQ"


def resample(samples: np.ndarray, from_rate: int, to_rate: int) -> np.ndarray:
    """Convert a whole float audio buffer from one sample rate to another.

    Args:
        samples: Mono `(n,)` or multi-channel `(n, channels)` audio.
        from_rate: The buffer's sample rate in Hz.
        to_rate: The wanted sample rate in Hz.

    Returns:
        float32 audio at `to_rate`, with the same channel layout. If the rates
        are equal the input comes back as float32 without being copied.

    Raises:
        ValueError: If either rate is not positive.
    """
    _require_positive_rate(from_rate)
    _require_positive_rate(to_rate)
    audio = np.asarray(samples, dtype=np.float32)
    if from_rate == to_rate or audio.shape[0] == 0:
        return audio
    return soxr.resample(audio, from_rate, to_rate, quality=SOXR_QUALITY).astype(
        np.float32, copy=False
    )


class StreamResampler:
    """Resample a continuous mono float32 stream one block at a time.

    Output lags input by the filter delay, so early calls may return fewer
    samples (even none). Create a new instance to start a fresh stream.
    """

    def __init__(self, from_rate: int, to_rate: int) -> None:
        """Set up the converter.

        Args:
            from_rate: Input sample rate in Hz.
            to_rate: Output sample rate in Hz.

        Raises:
            ValueError: If either rate is not positive.
        """
        _require_positive_rate(from_rate)
        _require_positive_rate(to_rate)
        # Equal rates skip soxr entirely and pass blocks through.
        self._stream = (
            None
            if from_rate == to_rate
            else soxr.ResampleStream(from_rate, to_rate, 1, dtype="float32", quality=SOXR_QUALITY)
        )

    def process(self, block: np.ndarray) -> np.ndarray:
        """Feed one mono block and return whatever output is ready (float32)."""
        audio = np.asarray(block, dtype=np.float32)
        if self._stream is None:
            return audio
        return self._stream.resample_chunk(audio)


def _require_positive_rate(rate: int) -> None:
    if rate <= 0:
        raise ValueError(f"sample rate must be positive, got {rate}")
