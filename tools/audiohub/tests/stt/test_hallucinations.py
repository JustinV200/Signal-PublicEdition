"""Tests for audiohub.stt.hallucinations: the Whisper silence-hallucination filter."""

import pytest

from audiohub.stt.hallucinations import remove_hallucinations


@pytest.mark.parametrize(
    "transcript",
    [
        " Thank you.",
        "you",
        "Thanks for watching!",
        "you you you you",
        "Thank you. Thank you. Thank you.",
        "Subtitles by the Amara.org community",
        "Don’t forget to like and subscribe.",
        "[Music]",
        "♪♪",
        "[BLANK_AUDIO] Thank you.",
        "",
    ],
)
def test_pure_hallucinations_become_empty(transcript: str) -> None:
    assert remove_hallucinations(transcript) == ""


@pytest.mark.parametrize(
    "transcript",
    [
        "Hey Claude, thank you.",
        "Claude, what's the weather like?",
        "Okay.",
        "Thank you, Claude.",
    ],
)
def test_real_speech_is_kept(transcript: str) -> None:
    assert remove_hallucinations(transcript) == transcript


def test_outro_sentence_is_removed_from_real_speech() -> None:
    text = "What's the weather in London? Thanks for watching!"
    assert remove_hallucinations(text) == "What's the weather in London?"


def test_filler_sentence_next_to_real_speech_is_kept() -> None:
    text = "Thank you. Now play some music."
    assert remove_hallucinations(text) == text


def test_sound_tags_are_removed_from_real_speech() -> None:
    assert remove_hallucinations("(music) Hello there. [Music]") == "Hello there."
