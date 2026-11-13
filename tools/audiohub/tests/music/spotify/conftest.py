"""Fixtures for Spotify backend tests: a fake spotipy client and a real SpotifyAuth.

`spotify_auth` is the real SpotifyAuth over a temporary token cache holding an
unexpired token, so spotipy validates it locally and never touches the network.
"""

import json
import logging
import time
from pathlib import Path
from typing import Any

import pytest
from spotipy.exceptions import SpotifyException

from audiohub.config import MusicSettings
from audiohub.music.spotify import CLIENT_ID_ENV_VAR, SCOPES, SpotifyAuth, SpotifyController
from audiohub.music.spotify.errors import SPOTIPY_LOGGER_NAME

SPOTIPY_LOGGER = logging.getLogger(SPOTIPY_LOGGER_NAME)
CACHED_ACCESS_TOKEN = "cached-access-token"
TEST_CLIENT_ID = "test-client-id"
ONE_HOUR_S = 3600


def no_active_device_error() -> SpotifyException:
    """The error Spotify's player endpoints give when no device is active."""
    return SpotifyException(404, -1, "No active device found", reason="NO_ACTIVE_DEVICE")


class FakeSpotifyApi:
    """Stands in for spotipy.Spotify: records calls and returns scripted data.

    `failures` maps a method name to the exception it raises. `tokens` lists
    every token passed to set_auth, in order. With `has_active_device` False,
    player commands without a device_id fail like Spotify's NO_ACTIVE_DEVICE,
    and `devices_response` is what `devices()` lists.
    """

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.tokens: list[str] = []
        self.failures: dict[str, Exception] = {}
        self.playback: dict[str, Any] | None = None
        self.search_results: dict[str, Any] = {}
        self.has_active_device = True
        # True: pause_playback succeeds but current_playback keeps saying playing.
        self.ignores_pause = False
        self.devices_response: dict[str, Any] = {"devices": []}
        self.profile: dict[str, Any] = {"id": "owner"}

    def _record(self, method: str, **kwargs: Any) -> None:
        self.calls.append((method, kwargs))
        failure = self.failures.get(method)
        if failure is None:
            return
        if isinstance(failure, SpotifyException):
            # Like spotipy, which logs every HTTP error at ERROR before raising it.
            SPOTIPY_LOGGER.error(
                "HTTP Error for %s returned %s due to %s", method, failure.http_status, failure.msg
            )
        raise failure

    def _player(self, method: str, device_id: str | None, **kwargs: Any) -> None:
        self._record(method, device_id=device_id, **kwargs)
        if device_id is None and not self.has_active_device:
            raise no_active_device_error()

    def set_auth(self, auth: str) -> None:
        self.tokens.append(auth)

    def start_playback(self, device_id: str | None = None, **kwargs: Any) -> None:
        self._player("start_playback", device_id, **kwargs)

    def pause_playback(self, device_id: str | None = None) -> None:
        self._player("pause_playback", device_id)
        if self.playback is not None and not self.ignores_pause:
            self.playback = {**self.playback, "is_playing": False}

    def next_track(self, device_id: str | None = None) -> None:
        self._player("next_track", device_id)

    def previous_track(self, device_id: str | None = None) -> None:
        self._player("previous_track", device_id)

    def volume(self, volume_percent: int, device_id: str | None = None) -> None:
        self._player("volume", device_id, volume_percent=volume_percent)

    def current_playback(self) -> dict[str, Any] | None:
        self._record("current_playback")
        return self.playback

    def devices(self) -> dict[str, Any]:
        self._record("devices")
        return self.devices_response

    def transfer_playback(self, device_id: str, force_play: bool = True) -> None:
        self._record("transfer_playback", device_id=device_id, force_play=force_play)

    def search(self, q: str, limit: int, type: str) -> dict[str, Any]:
        self._record("search", q=q, limit=limit, type=type)
        return self.search_results

    def add_to_queue(self, uri: str, device_id: str | None = None) -> None:
        self._player("add_to_queue", device_id, uri=uri)

    def shuffle(self, state: bool, device_id: str | None = None) -> None:
        self._player("shuffle", device_id, state=state)

    def current_user(self) -> dict[str, Any]:
        self._record("current_user")
        return self.profile


def write_token_cache(path: Path, *, expires_in_s: int = ONE_HOUR_S, scopes=SCOPES) -> Path:
    """Write a spotipy-format token cache file and return its path."""
    token_info = {
        "access_token": CACHED_ACCESS_TOKEN,
        "token_type": "Bearer",
        "expires_in": ONE_HOUR_S,
        "expires_at": int(time.time()) + expires_in_s,
        "refresh_token": "cached-refresh-token",
        "scope": " ".join(scopes),
    }
    path.write_text(json.dumps(token_info), encoding="utf-8")
    return path


@pytest.fixture(autouse=True)
def no_pause_check_delay(monkeypatch) -> None:
    """Skip the real wait between pause-confirmation reads."""
    monkeypatch.setattr("audiohub.music.spotify.controller.PAUSE_CHECK_DELAY_S", 0)


@pytest.fixture
def make_token_cache():
    """Return write_token_cache, for tests that need an expired or narrow token."""
    return write_token_cache


@pytest.fixture
def token_cache(tmp_path) -> Path:
    """A token cache path holding a valid, unexpired token."""
    return write_token_cache(tmp_path / "token.json")


@pytest.fixture
def spotify_auth(token_cache) -> SpotifyAuth:
    """A real SpotifyAuth with a client ID set and a valid cached token."""
    environ = {CLIENT_ID_ENV_VAR: TEST_CLIENT_ID}
    return SpotifyAuth(MusicSettings(), environ=environ, cache_path=token_cache)


@pytest.fixture
def fake_api() -> FakeSpotifyApi:
    return FakeSpotifyApi()


@pytest.fixture
def spotify(spotify_auth, fake_api) -> SpotifyController:
    """A SpotifyController over the fake client, logged in."""
    return SpotifyController(MusicSettings(), auth=spotify_auth, api=fake_api)
