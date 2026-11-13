"""Silero voice-activity detection for single 512-sample frames.

Wraps `pysilero_vad.SileroVoiceActivityDetector` (ggml build of Silero v6,
CPU, ~0.05 ms per frame). A `LevelNormalizer` lifts quiet Bluetooth-mic input
before scoring. The segmenter (segmenter.py) turns these per-frame scores into
utterances.
"""

import numpy as np
from pysilero_vad import SileroVoiceActivityDetector

from audiohub.stt.frames import FRAME_MS, validate_frame
from audiohub.stt.level import LevelNormalizer


class VoiceActivityDetector:
    """Scores how likely each frame is to contain speech.

    Silero is a recurrent model, so frames must arrive in order. Call
    `reset()` after a gap in the stream (e.g. the mic was paused).
    """

    def __init__(self, threshold: float, normalizer: LevelNormalizer | None = None) -> None:
        """Load the bundled Silero model.

        Args:
            threshold: Speech probability at or above which a frame counts as
                speech, in [0, 1]. Used by the segmenter.
            normalizer: Gain stage applied before scoring. Defaults to a
                `LevelNormalizer` with its standard settings.

        Raises:
            ValueError: If `threshold` is outside [0, 1].
        """
        if not 0.0 <= threshold <= 1.0:
            raise ValueError(f"VAD threshold must be in [0, 1], got {threshold}")
        self._threshold = threshold
        self._normalizer = normalizer or LevelNormalizer(FRAME_MS)
        self._model = SileroVoiceActivityDetector()

    @property
    def threshold(self) -> float:
        """Speech probability at or above which a frame counts as speech."""
        return self._threshold

    def speech_probability(self, frame: np.ndarray) -> float:
        """Return the probability, in [0, 1], that `frame` contains speech.

        Args:
            frame: float32 mono 16 kHz samples, exactly FRAME_SAMPLES long.

        Returns:
            Silero's speech probability for the normalised frame.

        Raises:
            ValueError: If the frame has the wrong shape.
        """
        samples = self._normalizer.apply(validate_frame(frame))
        return float(self._model.process_samples(samples))

    def reset(self) -> None:
        """Clear Silero's recurrent state and the normaliser's tracked level."""
        self._model.reset()
        self._normalizer.reset()
