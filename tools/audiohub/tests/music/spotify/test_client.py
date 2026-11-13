"""Tests for audiohub.music.spotify.client: executor calls, per-call tokens, error mapping."""

import pytest
import spotipy
from spotipy.exceptions import SpotifyException

from audiohub.music import MusicUnavailable, UnavailableReason
from audiohub.music.spotify.client import SpotifyCaller, create_spotify_api


class FixedTokens:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error

    def access_token(self) -> str:
        if self.error is not None:
            raise self.error
        return "fresh-token"


@pytest.mark.asyncio
async def test_call_sets_the_token_then_returns_the_result(fake_api):
    caller = SpotifyCaller(FixedTokens(), fake_api)
    fake_api.playback = {"is_playing": True}
    assert await caller.call(lambda api: api.current_playback()) == {"is_playing": True}
    assert fake_api.tokens == ["fresh-token"]


@pytest.mark.asyncio
async def test_auth_problems_stop_the_call(fake_api):
    not_logged_in = MusicUnavailable("log in", UnavailableReason.NOT_LOGGED_IN)
    caller = SpotifyCaller(FixedTokens(error=not_logged_in), fake_api)
    with pytest.raises(MusicUnavailable) as error:
        await caller.call(lambda api: api.pause_playback())
    assert error.value is not_logged_in
    assert fake_api.calls == []


@pytest.mark.asyncio
async def test_spotify_errors_are_mapped(fake_api):
    fake_api.failures["pause_playback"] = SpotifyException(404, -1, "", reason="NO_ACTIVE_DEVICE")
    caller = SpotifyCaller(FixedTokens(), fake_api)
    with pytest.raises(MusicUnavailable) as error:
        await caller.call(lambda api: api.pause_playback())
    assert error.value.reason is UnavailableReason.NO_ACTIVE_DEVICE
    assert isinstance(error.value.__cause__, SpotifyException)


@pytest.mark.asyncio
async def test_network_errors_are_mapped(fake_api):
    fake_api.failures["next_track"] = ConnectionError("dns failure")
    caller = SpotifyCaller(FixedTokens(), fake_api)
    with pytest.raises(MusicUnavailable, match="couldn't reach Spotify") as error:
        await caller.call(lambda api: api.next_track())
    assert error.value.reason is UnavailableReason.REQUEST_FAILED


def test_real_client_fails_fast_on_rate_limits():
    api = create_spotify_api()
    assert isinstance(api, spotipy.Spotify)
    assert api.status_retries == 0
    assert api.status_forcelist == (429,)
