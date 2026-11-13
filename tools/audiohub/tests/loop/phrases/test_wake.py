"""Tests for match_wake: wake phrases, mis-hearings, punctuation and false positives."""

import pytest

from audiohub.loop.phrases import match_wake

PHRASES = ("hey claude", "claude", "hey signal")


@pytest.mark.parametrize(
    ("transcript", "expected"),
    [
        ("Hey Claude, what's the weather like in London today?",
         "what's the weather like in London today?"),
        ("HEY, CLAUDE! Play some jazz.", "Play some jazz."),
        ("Claude, turn it up.", "turn it up."),
        ("Hey-Claude: read my email", "read my email"),
    ],
)  # fmt: skip
def test_leading_wake_phrase_is_stripped(transcript, expected):
    assert match_wake(transcript, PHRASES) == expected


@pytest.mark.parametrize(
    "transcript",
    [
        "Hey cloud, what's the time?",
        "Clawed, what's the time?",
        "Hi Claude, what's the time?",
        "Clod, what's the time?",
        "Hey Signal, what's the time?",
        "hey cygnal, what's the time?",
        "Hey signals, what's the time?",
    ],
)
def test_common_mishearings_wake_claude(transcript):
    assert match_wake(transcript, PHRASES) == "what's the time?"


def test_curly_apostrophes_are_handled():
    assert match_wake("Hey Claude’s friend", ("hey claude",)) is None
    assert match_wake("Hey Claude, it’s late", PHRASES) == "it’s late"


@pytest.mark.parametrize(
    "transcript",
    [
        "Cloud storage is down again.",
        "The cat clawed at the sofa, apparently.",
        "The signal is bad.",
        "Signal strength is low.",
        "Thanks, Signals",
        "Signal, what's the time?",
        "Is it a single, what's the time?",
        "",
    ],
)
def test_not_addressing_claude_returns_none(transcript):
    assert match_wake(transcript, PHRASES) is None


def test_wake_phrase_mid_sentence_does_not_count():
    assert match_wake("I told Claude about it yesterday", PHRASES) is None


@pytest.mark.parametrize("transcript", ["Hey Claude.", "Claude?", "hey, cloud", "Okay, Claude!"])
def test_wake_phrase_alone_gives_empty_request(transcript):
    assert match_wake(transcript, PHRASES) == ""


def test_leading_fillers_are_skipped():
    assert match_wake("Um, okay, hey Claude, what's next?", PHRASES) == "what's next?"


def test_trailing_wake_after_comma_keeps_question_mark():
    assert match_wake("What's the time, Claude?", PHRASES) == "What's the time?"
    assert match_wake("Turn it down a bit, hey Claude.", PHRASES) == "Turn it down a bit."


def test_trailing_wake_needs_a_comma():
    assert match_wake("I was talking to Claude", PHRASES) is None


def test_trailing_bare_cloud_is_not_a_wake_word():
    assert match_wake("Is it going to rain, cloud?", PHRASES) is None


def test_longer_phrase_wins_over_its_suffix():
    # Phrase order in the config doesn't matter: "hey claude" is stripped whole.
    assert match_wake("Hey Claude, hello", ("claude", "hey claude")) == "hello"


def test_custom_phrase_without_soundalikes():
    assert match_wake("Computer, lights on.", ("computer",)) == "lights on."
    assert match_wake("Computers are great", ("computer",)) is None


def test_blank_phrases_are_ignored():
    assert match_wake("Hello there", ("", "  ", "!!")) is None


def test_signal_works_as_trailing_vocative():
    assert match_wake("Thanks, Signal", PHRASES) == "Thanks"
    assert match_wake("What's the time, signal?", PHRASES) == "What's the time?"
