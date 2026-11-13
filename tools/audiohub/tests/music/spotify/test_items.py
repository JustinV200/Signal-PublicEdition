"""Tests for audiohub.music.spotify.items: reading search results and describing items."""

import pytest

from audiohub.music.spotify.items import artist_names, describe_item, first_match

TRACK = {
    "name": "Babydoll",
    "uri": "spotify:track:1",
    "artists": [{"name": "Dominic Fike"}, {"name": "Guest"}],
}


def test_artist_names_are_joined():
    assert artist_names(TRACK) == "Dominic Fike, Guest"


@pytest.mark.parametrize("item", [{}, {"artists": "nope"}, {"artists": [None, {"name": ""}]}])
def test_odd_artist_lists_give_an_empty_string(item):
    assert artist_names(item) == ""


@pytest.mark.parametrize(
    ("kind", "item", "expected"),
    [
        ("track", TRACK, "Babydoll by Dominic Fike, Guest"),
        (
            "album",
            {"name": "Sunburn", "artists": [{"name": "Dominic Fike"}]},
            "the album Sunburn by Dominic Fike",
        ),
        ("playlist", {"name": "Chill Mix"}, "the playlist Chill Mix"),
        ("artist", {"name": "Dominic Fike"}, "songs by Dominic Fike"),
    ],
)
def test_items_are_described_for_speech(kind, item, expected):
    assert describe_item(item, kind) == expected


def test_first_match_skips_null_and_uri_less_entries():
    playlist = {"name": "Chill Mix", "uri": "spotify:playlist:9"}
    results = {"playlists": {"items": [None, {"name": "no uri"}, playlist]}}
    match = first_match(results, "playlist")
    assert match is not None
    assert match.uri == "spotify:playlist:9"
    assert match.description == "the playlist Chill Mix"


@pytest.mark.parametrize("results", [{}, {"tracks": None}, {"tracks": {"items": []}}])
def test_no_usable_results_gives_none(results):
    assert first_match(results, "track") is None


def test_first_match_prefers_the_item_whose_name_is_in_the_query():
    results = {
        "tracks": {
            "items": [
                {"name": "YEAH RIGHT", "uri": "spotify:track:right", "artists": []},
                {"name": "ATTENTION", "uri": "spotify:track:attention", "artists": []},
            ]
        }
    }
    assert first_match(results, "track", "Attention Joji").uri == "spotify:track:attention"
    assert first_match(results, "track", "something else").uri == "spotify:track:right"
