"""Slow automatic gain that lifts quiet microphone input before VAD.

The Bluetooth audio glasses' Bluetooth Hands-Free mic is narrowband and often very
quiet, and Silero scores faint speech low. Measured with an 8 kHz-limited
speech clip: at peak 0.003 Silero alone clips the utterance (2.2 s of 3.5 s),
and at 0.002 it misses it entirely. With this gain stage, both come through
whole. The normaliser follows the recent peak level and boosts quiet input
towards a target peak, with a capped gain.
It feeds only the VAD. Whisper gets the raw audio, because its log-mel front
end already normalises the level.
"""

import numpy as np

# These tunables stay in code, not config: the brief fixes the [vad] schema, and
# they are matched to Silero's behaviour rather than to any one machine.

# Peak level that boosted speech is aimed at (full scale = 1.0).
TARGET_PEAK = 0.5

# Never boost by more than 20 dB, so a silent room's noise floor stays quiet.
MAX_GAIN = 10.0

# The tracked peak halves every ~3 s without louder input. That is slow enough
# that gain doesn't pump between words, and fast enough to follow a level change.
PEAK_HALF_LIFE_MS = 3000.0

# Floor on the tracked peak, so the gain stays finite on digital silence.
_MIN_TRACKED_PEAK = 1e-6


class LevelNormalizer:
    """Stateful gain stage that is fed one frame at a time.

    Attributes are fixed at construction; `reset()` clears the tracked peak.
    """

    def __init__(
        self,
        frame_ms: float,
        target_peak: float = TARGET_PEAK,
        max_gain: float = MAX_GAIN,
    ) -> None:
        """Create a normaliser for frames of a known duration.

        Args:
            frame_ms: Duration of each frame passed to `apply`, in milliseconds.
            target_peak: Peak level that quiet input is boosted towards.
            max_gain: Upper limit on the applied gain (linear, >= 1).

        Raises:
            ValueError: If an argument is out of range.
        """
        if frame_ms <= 0 or not 0 < target_peak <= 1 or max_gain < 1:
            raise ValueError("need frame_ms > 0, 0 < target_peak <= 1 and max_gain >= 1")
        self._target_peak = target_peak
        self._max_gain = max_gain
        self._decay_per_frame = 0.5 ** (frame_ms / PEAK_HALF_LIFE_MS)
        self._tracked_peak = 0.0

    def apply(self, frame: np.ndarray) -> np.ndarray:
        """Return a gain-adjusted copy of `frame` and update the tracked peak.

        Gain is never below 1, so loud input passes through unchanged. The
        current frame counts towards the tracked peak before the gain is
        chosen, so a sudden loud onset is not boosted into clipping.

        Args:
            frame: float32 mono samples in [-1, 1].

        Returns:
            A new float32 array of the same shape, clipped to [-1, 1].
        """
        frame_peak = float(np.max(np.abs(frame))) if frame.size else 0.0
        self._tracked_peak = max(frame_peak, self._tracked_peak * self._decay_per_frame)
        gain = self._target_peak / max(self._tracked_peak, _MIN_TRACKED_PEAK)
        gain = min(max(gain, 1.0), self._max_gain)
        return np.clip(frame * np.float32(gain), -1.0, 1.0).astype(np.float32)

    def reset(self) -> None:
        """Forget the tracked peak, e.g. after the mic was paused."""
        self._tracked_peak = 0.0
