"""Tests for audiohub.music.spotify.controller: SpotifyController over a fake spotipy client."""

import logging
from contextlib import nullcontext

import pytest
from spotipy.exceptions import SpotifyException

from audiohub.music import MusicUnavailable, NowPlaying, UnavailableReason
from audiohub.music.spotify import SEARCH_LIMIT

BABYDOLL = {
    "name": "Babydoll",
    "uri": "spotify:track:babydoll",
    "artists": [{"name": "Dominic Fike"}],
}

PHONE = {"id": "phone-1", "type": "Smartphone", "is_restricted": False}
THIS_PC = {"id": "pc-1", "type": "Computer", "is_restricted": False}
LIKED_SONGS_URI = "spotify:user:owner:collection"

# (controller call, the spotipy method it sends, that method's other kwargs)
PLAYER_COMMANDS = [
    (lambda spotify: spotify.play(), "start_playback", {}),
    (lambda spotify: spotify.pause(), "pause_playback", {}),
    (lambda spotify: spotify.next(), "next_track", {}),
    (lambda spotify: spotify.previous(), "previous_track", {}),
    (lambda spotify: spotify.set_volume(35), "volume", {"volume_percent": 35}),
]


def method_names(fake_api) -> list[str]:
    return [method for method, _kwargs in fake_api.calls]


def commands_sent(fake_api) -> list[tuple[str, dict]]:
    """The calls made, minus the state reads that pause makes to confirm itself."""
    return [call for call in fake_api.calls if call[0] != "current_playback"]


@pytest.fixture
def idle_pc(fake_api):
    """Spotify is open on this PC (and a phone) but no device is active."""
    fake_api.has_active_device = False
    fake_api.devices_response = {"devices": [PHONE, THIS_PC]}
    return fake_api


@pytest.mark.asyncio
@pytest.mark.parametrize(("send", "api_method", "kwargs"), PLAYER_COMMANDS)
async def test_player_commands_go_to_the_active_device(spotify, fake_api, send, api_method, kwargs):
    await send(spotify)
    assert commands_sent(fake_api) == [(api_method, {"device_id": None, **kwargs})]
    assert set(fake_api.tokens) == {"cached-access-token"}


@pytest.mark.asyncio
@pytest.mark.parametrize(("send", "api_method", "kwargs"), PLAYER_COMMANDS)
async def test_idle_app_is_woken_preferring_the_computer(
    spotify, idle_pc, send, api_method, kwargs
):
    await send(spotify)
    assert commands_sent(idle_pc) == [
        (api_method, {"device_id": None, **kwargs}),
        ("devices", {}),
        ("transfer_playback", {"device_id": "pc-1", "force_play": False}),
        (api_method, {"device_id": "pc-1", **kwargs}),
    ]


@pytest.mark.asyncio
async def test_closed_app_is_still_no_active_device(spotify, fake_api):
    fake_api.has_active_device = False
    with pytest.raises(MusicUnavailable, match="open the Spotify app") as error:
        await spotify.next()
    assert error.value.reason is UnavailableReason.NO_ACTIVE_DEVICE
    assert method_names(fake_api) == ["next_track", "devices"]


@pytest.mark.asyncio
async def test_other_errors_are_not_retried_on_another_device(spotify, fake_api):
    fake_api.failures["start_playback"] = SpotifyException(403, -1, "", reason="PREMIUM_REQUIRED")
    with pytest.raises(MusicUnavailable) as error:
        await spotify.play()
    assert error.value.reason is UnavailableReason.PREMIUM_REQUIRED
    assert method_names(fake_api) == ["start_playback"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("playback", "expected"),
    [
        ({"is_playing": True, "item": BABYDOLL}, "pause_playback"),
        ({"is_playing": False, "item": BABYDOLL}, "start_playback"),
        # Episodes and ads have no track item, but is_playing still counts.
        ({"is_playing": True, "item": None, "currently_playing_type": "episode"}, "pause_playback"),
    ],
)
async def test_toggle_reads_is_playing(spotify, fake_api, playback, expected):
    fake_api.playback = playback
    await spotify.toggle()
    assert [m for m in method_names(fake_api) if m != "current_playback"] == [expected]
    assert method_names(fake_api)[0] == "current_playback"


@pytest.mark.asyncio
async def test_toggle_on_an_idle_app_starts_it(spotify, idle_pc):
    idle_pc.playback = None
    await spotify.toggle()
    assert idle_pc.calls[-1] == ("start_playback", {"device_id": "pc-1"})


@pytest.mark.asyncio
async def test_now_playing_reads_the_current_track(spotify, fake_api):
    fake_api.playback = {"is_playing": True, "item": BABYDOLL}
    assert await spotify.now_playing() == NowPlaying(
        "Babydoll", "Dominic Fike", "", is_playing=True, source="spotify"
    )


@pytest.mark.asyncio
async def test_no_playback_state_means_no_active_device(spotify, fake_api):
    fake_api.playback = None
    with pytest.raises(MusicUnavailable, match="open the Spotify app") as error:
        await spotify.now_playing()
    assert error.value.reason is UnavailableReason.NO_ACTIVE_DEVICE


@pytest.mark.asyncio
async def test_bad_volume_is_rejected_before_any_call(spotify, fake_api):
    with pytest.raises(ValueError):
        await spotify.set_volume(150)
    assert fake_api.calls == []


@pytest.mark.asyncio
async def test_search_and_play_a_track_plays_its_uri(spotify, fake_api):
    fake_api.search_results = {"tracks": {"items": [BABYDOLL]}}
    assert await spotify.search_and_play("  babydoll ") == "Babydoll by Dominic Fike"
    search, play = fake_api.calls
    assert search == (
        "search",
        {
            "q": "babydoll",
            "limit": SEARCH_LIMIT,
            "type": "track",
        },  # no "market": from_token needs a scope we lack
    )
    assert play == ("start_playback", {"device_id": None, "uris": ["spotify:track:babydoll"]})


@pytest.mark.asyncio
async def test_search_and_play_an_album_on_an_idle_app(spotify, idle_pc):
    album = {"name": "Sunburn", "uri": "spotify:album:sunburn", "artists": []}
    idle_pc.search_results = {"albums": {"items": [album]}}
    assert await spotify.search_and_play("sunburn", "album") == "the album Sunburn"
    assert idle_pc.calls[-1] == (
        "start_playback",
        {"device_id": "pc-1", "context_uri": "spotify:album:sunburn"},
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("shuffle", "expected_shuffle_calls", "description"),
    [
        (None, [], "your Liked Songs"),
        (True, [("shuffle", {"device_id": "pc-1", "state": True})], "your Liked Songs on shuffle"),
    ],
)
async def test_play_liked_plays_the_saved_tracks_collection_not_a_search(
    spotify, idle_pc, shuffle, expected_shuffle_calls, description
):
    # Regression: "play my liked songs" went through search, which found a
    # stranger's playlist named "Liked Songs".
    assert await spotify.play_liked(shuffle) == description
    assert "search" not in method_names(idle_pc)
    start = ("start_playback", {"device_id": "pc-1", "context_uri": LIKED_SONGS_URI})
    # After waking the idle PC: shuffle (if asked) first, then the collection.
    assert idle_pc.calls[-len(expected_shuffle_calls) - 1 :] == [*expected_shuffle_calls, start]


@pytest.mark.asyncio
async def test_play_liked_without_a_user_id_plays_nothing(spotify, fake_api):
    fake_api.profile = {}
    with pytest.raises(MusicUnavailable, match="Liked Songs") as error:
        await spotify.play_liked()
    assert error.value.reason is UnavailableReason.REQUEST_FAILED
    assert method_names(fake_api) == ["current_user"]


@pytest.mark.asyncio
async def test_search_with_no_results_is_not_found(spotify, fake_api):
    fake_api.search_results = {"tracks": {"items": []}}
    with pytest.raises(MusicUnavailable, match="couldn't find a track called zzz") as error:
        await spotify.search_and_play("zzz")
    assert error.value.reason is UnavailableReason.NOT_FOUND
    assert method_names(fake_api) == ["search"]


@pytest.mark.asyncio
async def test_bad_search_arguments_are_rejected_before_any_call(spotify, fake_api):
    with pytest.raises(ValueError):
        await spotify.search_and_play(" ")
    with pytest.raises(ValueError):
        await spotify.search_and_play("jazz", "podcast")
    assert fake_api.calls == []


@pytest.mark.asyncio
async def test_queue_adds_the_first_track_waking_an_idle_app(spotify, idle_pc):
    idle_pc.search_results = {"tracks": {"items": [BABYDOLL]}}
    assert await spotify.queue("babydoll") == "Babydoll by Dominic Fike"
    assert idle_pc.calls[-1] == (
        "add_to_queue",
        {"device_id": "pc-1", "uri": "spotify:track:babydoll"},
    )


@pytest.mark.asyncio
async def test_pause_that_spotify_ignores_is_reported(spotify, fake_api):
    fake_api.playback = {"is_playing": True, "item": BABYDOLL}
    fake_api.ignores_pause = True
    with pytest.raises(MusicUnavailable, match="still playing"):
        await spotify.pause()
    assert method_names(fake_api).count("current_playback") == 3


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("is_playing", "outcome", "is_logged_loudly"),
    [
        (False, nullcontext(), False),
        (
            True,
            pytest.raises(
                MusicUnavailable, check=lambda error: error.reason is UnavailableReason.RESTRICTED
            ),
            True,
        ),
    ],
    ids=["already paused", "playing"],
)
async def test_a_refused_pause_succeeds_only_if_the_music_is_paused(
    spotify, fake_api, caplog, is_playing, outcome, is_logged_loudly
):
    # Spotify refuses to pause a paused player; the hub may have paused it already.
    # That expected refusal stays out of the WARNING log; a real one doesn't.
    fake_api.playback = {"is_playing": is_playing, "item": BABYDOLL}
    fake_api.failures["pause_playback"] = SpotifyException(
        403, -1, "Player command failed: Restriction violated", reason="UNKNOWN"
    )
    with outcome:
        await spotify.pause()
    assert "pause_playback" in method_names(fake_api)
    loud_records = [record for record in caplog.records if record.levelno >= logging.WARNING]
    assert bool(loud_records) is is_logged_loudly


@pytest.mark.asyncio
async def test_pause_then_now_playing_agree(spotify, fake_api):
    fake_api.playback = {"is_playing": True, "item": BABYDOLL}
    await spotify.pause()
    assert (await spotify.now_playing()).is_playing is False
