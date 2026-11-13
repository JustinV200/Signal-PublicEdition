"""Tests for audiohub.music.spotify.playback: playback-state responses become NowPlaying."""

from audiohub.music import NowPlaying
from audiohub.music.spotify.playback import parse_playback


def test_full_response_is_parsed():
    playback = {
        "is_playing": True,
        "item": {
            "name": "Babydoll",
            "artists": [{"name": "Dominic Fike"}],
            "album": {"name": "Don't Forget About Me, Demos"},
        },
    }
    assert parse_playback(playback) == NowPlaying(
        title="Babydoll",
        artist="Dominic Fike",
        album="Don't Forget About Me, Demos",
        is_playing=True,
        source="spotify",
    )


def test_device_with_nothing_loaded_gives_none():
    assert parse_playback({"is_playing": False, "item": None}) is None


def test_missing_fields_become_empty_strings():
    current = parse_playback({"item": {}})
    assert current == NowPlaying("", "", "", is_playing=False, source="spotify")
