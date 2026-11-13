"""Audio frame format shared by the VAD and the utterance segmenter.

The microphone (audiohub.audio) delivers float32 mono 16 kHz frames of 512
samples, which is the only window size Silero VAD v5+ accepts. Everything in
audiohub.stt assumes that format, so the constants and the check live here once.
"""

import numpy as np

# Whisper and Silero both want 16 kHz mono input.
SAMPLE_RATE = 16_000

# Silero VAD's fixed window: 512 samples = 32 ms at 16 kHz.
FRAME_SAMPLES = 512

FRAME_MS = FRAME_SAMPLES * 1000 / SAMPLE_RATE


def validate_frame(frame: np.ndarray) -> np.ndarray:
    """Check that `frame` is one VAD frame and return it as contiguous float32.

    Args:
        frame: Mono audio, expected shape (FRAME_SAMPLES,), values in [-1, 1].

    Returns:
        The same samples as a contiguous float32 array. No copy is made when
        the input already has that layout.

    Raises:
        ValueError: If the frame is not 1-D with exactly FRAME_SAMPLES samples.
    """
    samples = np.ascontiguousarray(frame, dtype=np.float32)
    if samples.shape != (FRAME_SAMPLES,):
        raise ValueError(
            f"expected a mono frame of {FRAME_SAMPLES} samples, got shape {samples.shape}"
        )
    return samples
