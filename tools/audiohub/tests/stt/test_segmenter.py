"""Tests for audiohub.stt.segmenter: the utterance state machine.

A fake VAD reads each frame's speech probability from sample 0. Every other
sample holds a frame tag (its index in the fed sequence), so a test can see
exactly which input frames an utterance contains and in what order.

Test timings: 3 pre-roll frames, 4 min-speech frames, 5 min-silence frames,
and a 1 s cap (31 frames).
"""

import numpy as np
import pytest

from audiohub.config import VadSettings
from audiohub.stt import FRAME_SAMPLES, UtteranceSegmenter
from audiohub.stt.segmenter import HYSTERESIS, MIN_CONTINUE_THRESHOLD, SegmentLimits

SPEECH = 0.9
SILENCE = 0.0
FRAME_MS = 32

TEST_SETTINGS = VadSettings(
    threshold=0.5,
    pre_roll_ms=3 * FRAME_MS,
    min_speech_ms=4 * FRAME_MS,
    min_silence_ms=5 * FRAME_MS,
    max_utterance_s=1.0,
)
PRE_ROLL, MIN_SPEECH, MIN_SILENCE, MAX_FRAMES = 3, 4, 5, 31


class FakeScorer:
    """SpeechScorer whose probability is the frame's first sample value."""

    def __init__(self, threshold: float = 0.5) -> None:
        self.threshold = threshold
        self.reset_count = 0

    def speech_probability(self, frame: np.ndarray) -> float:
        return float(frame[0])

    def reset(self) -> None:
        self.reset_count += 1


def tagged_frame(probability: float, tag: int) -> np.ndarray:
    frame = np.full(FRAME_SAMPLES, float(tag), dtype=np.float32)
    frame[0] = probability
    return frame


def tags_of(utterance: np.ndarray) -> list[int]:
    return [int(tag) for tag in utterance.reshape(-1, FRAME_SAMPLES)[:, 1]]


def feed(segmenter: UtteranceSegmenter, probabilities: list[float], first_tag: int = 0) -> list:
    """Push one tagged frame per probability; return push() results in order."""
    return [
        segmenter.push(tagged_frame(probability, first_tag + offset))
        for offset, probability in enumerate(probabilities)
    ]


def emitted(results: list) -> list[np.ndarray]:
    return [result for result in results if result is not None]


@pytest.fixture
def scorer() -> FakeScorer:
    return FakeScorer()


@pytest.fixture
def segmenter(scorer: FakeScorer) -> UtteranceSegmenter:
    return UtteranceSegmenter(scorer, TEST_SETTINGS)


def test_limits_from_default_settings_round_up() -> None:
    # 300 ms -> 9.4 frames -> 10; 250 -> 7.8 -> 8; 700 -> 21.9 -> 22; 30 s -> 937.5 -> 937.
    assert SegmentLimits.from_settings(VadSettings()) == SegmentLimits(10, 8, 22, 937)


def test_zero_min_silence_still_needs_one_silent_frame() -> None:
    limits = SegmentLimits.from_settings(VadSettings(min_silence_ms=0))
    assert limits.min_silence_frames == 1


def test_silence_alone_never_emits(segmenter: UtteranceSegmenter) -> None:
    assert emitted(feed(segmenter, [SILENCE] * 100)) == []
    assert not segmenter.is_speaking


def test_utterance_ends_exactly_after_min_silence(segmenter: UtteranceSegmenter) -> None:
    results = feed(segmenter, [SPEECH] * 6 + [SILENCE] * MIN_SILENCE)
    assert all(result is None for result in results[:-1])
    assert results[-1] is not None


def test_utterance_has_pre_roll_speech_and_trimmed_tail(segmenter: UtteranceSegmenter) -> None:
    # Tags 0-9 silence, 10-15 speech, 16-20 silence.
    results = feed(segmenter, [SILENCE] * 10 + [SPEECH] * 6 + [SILENCE] * MIN_SILENCE)
    (utterance,) = emitted(results)
    # Pre-roll = the 3 frames before speech; the tail keeps 3 of the 5 silent frames.
    assert tags_of(utterance) == list(range(7, 19))


def test_pre_roll_is_shorter_when_speech_starts_immediately(
    segmenter: UtteranceSegmenter,
) -> None:
    (utterance,) = emitted(feed(segmenter, [SILENCE] + [SPEECH] * 6 + [SILENCE] * MIN_SILENCE))
    assert tags_of(utterance)[:2] == [0, 1]


@pytest.mark.parametrize(
    ("speech_frames", "is_kept"), [(MIN_SPEECH - 1, False), (MIN_SPEECH, True)]
)
def test_speech_shorter_than_min_speech_is_dropped(
    segmenter: UtteranceSegmenter, speech_frames: int, is_kept: bool
) -> None:
    results = feed(segmenter, [SPEECH] * speech_frames + [SILENCE] * 20)
    assert len(emitted(results)) == int(is_kept)
    assert not segmenter.is_speaking


def test_min_speech_counts_speech_frames_not_pauses(segmenter: UtteranceSegmenter) -> None:
    # 3 speech frames split by short pauses: long in time, but too little speech.
    pattern = [SPEECH, SILENCE, SILENCE, SPEECH, SILENCE, SILENCE, SPEECH]
    results = feed(segmenter, pattern + [SILENCE] * MIN_SILENCE)
    assert emitted(results) == []


def test_pause_shorter_than_min_silence_does_not_split(segmenter: UtteranceSegmenter) -> None:
    pattern = [SPEECH] * 5 + [SILENCE] * (MIN_SILENCE - 1) + [SPEECH] * 5
    (utterance,) = emitted(feed(segmenter, pattern + [SILENCE] * MIN_SILENCE))
    assert tags_of(utterance)[:14] == list(range(14))


def test_two_utterances_separated_by_a_long_pause(segmenter: UtteranceSegmenter) -> None:
    pattern = [SPEECH] * 5 + [SILENCE] * 10 + [SPEECH] * 5 + [SILENCE] * MIN_SILENCE
    first, second = emitted(feed(segmenter, pattern))
    assert tags_of(first)[0] == 0
    assert tags_of(second)[PRE_ROLL] == 15


def test_hysteresis_keeps_speech_going(segmenter: UtteranceSegmenter) -> None:
    weak = 0.5 - HYSTERESIS + 0.05  # below the start threshold, above the end one
    pattern = [SPEECH] * 4 + [weak] * 10 + [SILENCE] * MIN_SILENCE
    (utterance,) = emitted(feed(segmenter, pattern))
    assert tags_of(utterance)[:14] == list(range(14))


def test_weak_frames_cannot_start_speech(segmenter: UtteranceSegmenter) -> None:
    weak = 0.5 - HYSTERESIS + 0.05
    assert emitted(feed(segmenter, [weak] * 50)) == []
    assert not segmenter.is_speaking


@pytest.mark.parametrize("threshold", [0.12, 0.05])
def test_low_threshold_still_ends_on_silence(threshold: float) -> None:
    # Regression: the end threshold was floored at 0, so silence never ended speech.
    segmenter = UtteranceSegmenter(FakeScorer(threshold), TEST_SETTINGS)
    results = feed(segmenter, [SPEECH] * 5 + [SILENCE] * MIN_SILENCE)
    assert results[-1] is not None


def test_frames_below_the_floor_count_as_silence() -> None:
    segmenter = UtteranceSegmenter(FakeScorer(0.1), TEST_SETTINGS)
    below_floor = MIN_CONTINUE_THRESHOLD / 2
    results = feed(segmenter, [SPEECH] * 5 + [below_floor] * MIN_SILENCE)
    assert results[-1] is not None


def test_max_length_force_ends_continuous_speech(segmenter: UtteranceSegmenter) -> None:
    results = feed(segmenter, [SPEECH] * MAX_FRAMES)
    assert all(result is None for result in results[:-1])
    assert tags_of(results[-1]) == list(range(MAX_FRAMES))


def test_max_length_counts_the_pre_roll(segmenter: UtteranceSegmenter) -> None:
    results = feed(segmenter, [SILENCE] * PRE_ROLL + [SPEECH] * (MAX_FRAMES - PRE_ROLL))
    (utterance,) = emitted(results)
    assert len(tags_of(utterance)) == MAX_FRAMES


def test_speech_after_a_forced_end_does_not_repeat_audio(segmenter: UtteranceSegmenter) -> None:
    results = feed(segmenter, [SPEECH] * (MAX_FRAMES + 10) + [SILENCE] * MIN_SILENCE)
    first, second = emitted(results)
    assert tags_of(second)[0] == MAX_FRAMES
    assert not set(tags_of(first)) & set(tags_of(second))


def test_speech_right_after_a_natural_end_gets_pre_roll(segmenter: UtteranceSegmenter) -> None:
    pattern = [SPEECH] * 5 + [SILENCE] * MIN_SILENCE + [SPEECH] * 5 + [SILENCE] * MIN_SILENCE
    _, second = emitted(feed(segmenter, pattern))
    # The 3 silent frames that ended the first utterance (tags 7-9) lead the second.
    assert tags_of(second)[:4] == [7, 8, 9, 10]


def test_resumed_speech_does_not_repeat_the_previous_utterance(scorer: FakeScorer) -> None:
    # Regression: with min silence shorter than pre-roll, the next utterance's
    # pre-roll used to include speech that had already been emitted.
    settings = VadSettings(
        pre_roll_ms=5 * FRAME_MS, min_speech_ms=4 * FRAME_MS, min_silence_ms=2 * FRAME_MS
    )
    segmenter = UtteranceSegmenter(scorer, settings)
    # Tags 0-5 speech, 6-7 silence (ends it), 8-13 speech, 14-15 silence.
    pattern = [SPEECH] * 6 + [SILENCE] * 2 + [SPEECH] * 6 + [SILENCE] * 2
    first, second = emitted(feed(segmenter, pattern))
    assert tags_of(first) == list(range(8))
    assert tags_of(second) == list(range(6, 16))


def test_dropped_blip_becomes_pre_roll(segmenter: UtteranceSegmenter) -> None:
    pattern = [SPEECH] * 2 + [SILENCE] * MIN_SILENCE + [SPEECH] * 5 + [SILENCE] * MIN_SILENCE
    (utterance,) = emitted(feed(segmenter, pattern))
    assert tags_of(utterance)[:PRE_ROLL] == [4, 5, 6]


def test_reset_drops_partial_utterance_and_resets_vad(
    segmenter: UtteranceSegmenter, scorer: FakeScorer
) -> None:
    feed(segmenter, [SILENCE] * 5 + [SPEECH] * 10)
    segmenter.reset()
    assert not segmenter.is_speaking
    assert scorer.reset_count == 1
    assert emitted(feed(segmenter, [SILENCE] * MIN_SILENCE)) == []


def test_reset_clears_pre_roll(segmenter: UtteranceSegmenter) -> None:
    feed(segmenter, [SILENCE] * 5)  # the pre-roll is full of silence
    segmenter.reset()
    (utterance,) = emitted(feed(segmenter, [SPEECH] * 5 + [SILENCE] * MIN_SILENCE, first_tag=100))
    assert tags_of(utterance)[0] == 100


def test_push_copies_the_frame(segmenter: UtteranceSegmenter) -> None:
    reused_buffer = tagged_frame(SPEECH, 1)
    for _ in range(5):
        segmenter.push(reused_buffer)
    reused_buffer[1:] = 99.0  # the microphone overwrites its buffer
    (utterance,) = emitted(feed(segmenter, [SILENCE] * MIN_SILENCE))
    assert tags_of(utterance)[:5] == [1] * 5


def test_wrong_frame_shape_is_rejected(segmenter: UtteranceSegmenter) -> None:
    with pytest.raises(ValueError, match="512 samples"):
        segmenter.push(np.zeros(FRAME_SAMPLES - 1, dtype=np.float32))
