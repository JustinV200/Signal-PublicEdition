"""Utterance segmenter: turns a stream of VAD-scored frames into utterances.

A pure state machine with no I/O and no threads. The voice loop pushes each
microphone frame in. When an utterance has ended, `push` returns it as one
float32 16 kHz array, ready for the Transcriber. Timing comes from VadSettings:
- pre-roll: audio kept from before speech started, so soft onsets survive
- min speech: shorter bursts (coughs, clicks) are dropped
- min silence: how long a pause ends an utterance
- max utterance: a hard cap that force-ends very long speech
"""

import math
from collections import deque
from dataclasses import dataclass
from typing import Protocol

import numpy as np

from audiohub.config import VadSettings
from audiohub.stt.frames import FRAME_MS, validate_frame

# Once speech has started, frames keep counting as speech down to this much
# below the start threshold. Silero's reference segmenter uses the same 0.15
# gap. It stops a word's quiet tail from ending the utterance early.
HYSTERESIS = 0.15

# Floor on that end threshold, as in Silero's reference (max(t - 0.15, 0.01)).
# Without it a start threshold of 0.15 or less would make every frame count as
# speech, and utterances would only end at max_utterance_s.
MIN_CONTINUE_THRESHOLD = 0.01


class SpeechScorer(Protocol):
    """What the segmenter needs from a VAD. `VoiceActivityDetector` satisfies it."""

    @property
    def threshold(self) -> float:
        """Probability at or above which a frame starts speech."""
        ...

    def speech_probability(self, frame: np.ndarray) -> float:
        """Return the speech probability of one frame."""
        ...

    def reset(self) -> None:
        """Clear any per-stream state."""
        ...


@dataclass(frozen=True)
class SegmentLimits:
    """VadSettings timings converted to whole frame counts."""

    pre_roll_frames: int
    min_speech_frames: int
    min_silence_frames: int
    max_frames: int

    @classmethod
    def from_settings(cls, vad_settings: VadSettings) -> "SegmentLimits":
        """Round each duration up to whole frames (max length rounds down).

        Args:
            vad_settings: Validated VAD settings.

        Returns:
            The limits in frames. Silence needs at least one frame, and the
            maximum length leaves room for the pre-roll plus one frame.
        """
        pre_roll_frames = math.ceil(vad_settings.pre_roll_ms / FRAME_MS)
        max_frames = math.floor(vad_settings.max_utterance_s * 1000 / FRAME_MS)
        return cls(
            pre_roll_frames=pre_roll_frames,
            min_speech_frames=math.ceil(vad_settings.min_speech_ms / FRAME_MS),
            min_silence_frames=max(1, math.ceil(vad_settings.min_silence_ms / FRAME_MS)),
            max_frames=max(pre_roll_frames + 1, max_frames),
        )


class UtteranceSegmenter:
    """Collects frames into utterances using a VAD and VadSettings timings."""

    def __init__(self, vad: SpeechScorer, vad_settings: VadSettings) -> None:
        """Create an idle segmenter.

        Args:
            vad: Per-frame speech scorer; its `threshold` starts speech.
            vad_settings: Pre-roll, min speech, min silence and max length.
        """
        self._vad = vad
        self._limits = SegmentLimits.from_settings(vad_settings)
        self._continue_threshold = max(vad.threshold - HYSTERESIS, MIN_CONTINUE_THRESHOLD)
        # maxlen keeps only the most recent frames; maxlen=0 keeps none.
        self._pre_roll: deque[np.ndarray] = deque(maxlen=self._limits.pre_roll_frames)
        self._frames: list[np.ndarray] = []
        self._speech_frames = 0
        self._silence_run = 0

    @property
    def is_speaking(self) -> bool:
        """True while an utterance is being collected (speech has started)."""
        return bool(self._frames)

    def push(self, frame: np.ndarray) -> np.ndarray | None:
        """Feed one frame in; return a finished utterance if this frame ended one.

        Args:
            frame: float32 mono 16 kHz samples, exactly FRAME_SAMPLES long.

        Returns:
            The utterance (pre-roll + speech + up to pre-roll's worth of
            trailing silence) as one float32 array, or None if no utterance
            ended here. Utterances with less than min speech are dropped.

        Raises:
            ValueError: If the frame has the wrong shape.
        """
        # Copy: the microphone may reuse its buffers, and we keep frames around.
        samples = validate_frame(frame).copy()
        probability = self._vad.speech_probability(samples)
        if not self._frames:
            return self._push_while_idle(samples, probability)
        return self._push_while_speaking(samples, probability)

    def reset(self) -> None:
        """Drop any partial utterance and pre-roll, and reset the VAD's state."""
        self._pre_roll.clear()
        self._clear_utterance()
        self._vad.reset()

    def _push_while_idle(self, samples: np.ndarray, probability: float) -> np.ndarray | None:
        if probability < self._vad.threshold:
            self._pre_roll.append(samples)
            return None
        self._frames = [*self._pre_roll, samples]
        self._pre_roll.clear()
        self._speech_frames = 1
        return self._end_if_too_long()

    def _push_while_speaking(self, samples: np.ndarray, probability: float) -> np.ndarray | None:
        self._frames.append(samples)
        if probability >= self._continue_threshold:
            self._speech_frames += 1
            self._silence_run = 0
            return self._end_if_too_long()
        self._silence_run += 1
        if self._silence_run >= self._limits.min_silence_frames:
            return self._end_utterance(is_forced=False)
        return self._end_if_too_long()

    def _end_if_too_long(self) -> np.ndarray | None:
        if len(self._frames) < self._limits.max_frames:
            return None
        return self._end_utterance(is_forced=True)

    def _end_utterance(self, is_forced: bool) -> np.ndarray | None:
        frames = self._frames
        silence_run = self._silence_run
        is_long_enough = self._speech_frames >= self._limits.min_speech_frames
        # Keep at most a pre-roll's worth of trailing silence, so both ends of
        # the utterance get the same padding and Whisper sees less silence.
        excess_silence = max(0, silence_run - self._limits.pre_roll_frames)
        kept_frames = frames[: len(frames) - excess_silence]
        self._clear_utterance()
        # Seed the pre-roll for speech that starts straight away. After a forced
        # end the user is still talking, so nothing is seeded (it would repeat
        # audio). A dropped blip was never sent, so all of it may be pre-roll.
        # An emitted utterance contributes only its trailing silence; its
        # speech was already sent.
        if not is_forced:
            seed = frames if not is_long_enough else frames[len(frames) - silence_run :]
            self._pre_roll.extend(seed)
        if not is_long_enough:
            return None
        return np.concatenate(kept_frames)

    def _clear_utterance(self) -> None:
        self._frames = []
        self._speech_frames = 0
        self._silence_run = 0
