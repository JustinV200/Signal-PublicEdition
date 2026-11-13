"""Tests for the echo checks: is a transcript just the mic re-hearing Claude?"""

import pytest

from audiohub.loop.phrases import is_echo_during_speech, is_echo_of_ending

SPOKEN = "Claude here, so I've stopped the timer before it beeps."


@pytest.mark.parametrize(
    ("heard", "is_echo"),
    [
        ("Clawed here.", True),  # a misheard "Claude" is still Claude's own word
        ("Clawed, stop.", True),  # and "stop" starts Claude's "stopped"
        ("stopped the timer before, mate", True),  # 4 of 5 words: the 75% rule
        ("Stop the music now", False),  # 2 of 4 words
        ("Hey Claude, stop.", False),  # 2 of 3 words
        ("", False),
    ],
)
def test_echo_during_speech_forgives_mishearings_but_not_new_words(heard, is_echo):
    assert is_echo_during_speech(heard, SPOKEN) is is_echo


@pytest.mark.parametrize(
    ("heard", "spoken", "is_echo"),
    [
        # Regression: any reply made of words found anywhere in Claude's recent
        # sentences was dropped as an echo, so most follow-ups never got through.
        # Claude's words, but earlier in what it said:
        ("do it", "Should I do it now, or wait until tomorrow?", False),
        ("restart the server", "Should I restart the server or restart the database?", False),
        # Regression: Claude's exact last words with the user's "yes" in front
        # passed as an echo with one word Whisper added.
        ("Yes, delete the old logs.", "Should I go ahead and delete the old logs?", False),
        # Claude's last words, heard back:
        ("Clawed here.", "Hello, Claude here.", True),  # a wake-word soundalike
        ("stop it", "Right, I've stopped it.", True),  # a 4+ letter prefix
        # One misheard word in a long run is forgiven.
        (
            "the build passed and tree tests were skipped",
            "Done. The build passed and three tests were skipped.",
            True,
        ),
    ],
)
def test_echo_of_ending_is_claudes_last_words_in_order(heard, spoken, is_echo):
    assert is_echo_of_ending(heard, spoken) is is_echo
