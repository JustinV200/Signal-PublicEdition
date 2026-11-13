"""Tests for audiohub.music.now_playing: the speakable track description."""

import pytest

from audiohub.music import NowPlaying


@pytest.mark.parametrize(
    ("title", "artist", "expected"),
    [
        ("Babydoll", "Dominic Fike", "Babydoll by Dominic Fike"),
        ("Babydoll", "", "Babydoll"),
        ("", "Dominic Fike", "Dominic Fike"),
        ("", "", "an unnamed track"),
    ],
)
def test_describe_drops_unknown_parts(title, artist, expected):
    assert NowPlaying(title, artist, "", True, "spotify").describe() == expected
