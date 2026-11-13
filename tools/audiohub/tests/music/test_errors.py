"""Tests for audiohub.music.errors: the speakable message is the exception text."""

from audiohub.music import MusicUnavailable, UnavailableReason, UnsupportedOperation


def test_music_unavailable_speaks_its_message_and_keeps_the_reason():
    error = MusicUnavailable("Open the Spotify app.", UnavailableReason.NO_ACTIVE_DEVICE)
    assert str(error) == "Open the Spotify app."
    assert error.message == "Open the Spotify app."
    assert error.reason is UnavailableReason.NO_ACTIVE_DEVICE


def test_unsupported_operation_speaks_its_message():
    error = UnsupportedOperation("I can't do that.")
    assert str(error) == error.message == "I can't do that."
