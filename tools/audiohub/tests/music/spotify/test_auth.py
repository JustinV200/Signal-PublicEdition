"""Tests for audiohub.music.spotify.auth: client ID, cached tokens and login, with no network."""

import pytest
from spotipy.exceptions import SpotifyOauthError
from spotipy.oauth2 import SpotifyPKCE

from audiohub.config import MusicSettings
from audiohub.music import MusicUnavailable, UnavailableReason
from audiohub.music.spotify import CLIENT_ID_ENV_VAR, SCOPES, SpotifyAuth
from audiohub.music.spotify.auth import build_auth_manager, read_client_id

CLIENT_ENV = {CLIENT_ID_ENV_VAR: "abc123"}


def auth_with(cache_path, environ=None) -> SpotifyAuth:
    environ = CLIENT_ENV if environ is None else environ
    return SpotifyAuth(MusicSettings(), environ=environ, cache_path=cache_path)


def raiser(error: Exception):
    def raise_error(*_args, **_kwargs):
        raise error

    return raise_error


@pytest.mark.parametrize("environ", [{}, {CLIENT_ID_ENV_VAR: "  "}])
def test_missing_client_id_is_not_configured(environ):
    with pytest.raises(MusicUnavailable, match="SPOTIPY_CLIENT_ID") as error:
        read_client_id(environ)
    assert error.value.reason is UnavailableReason.NOT_CONFIGURED


def test_check_ready_reports_not_configured_first(tmp_path):
    with pytest.raises(MusicUnavailable) as error:
        auth_with(tmp_path / "token.json", environ={}).check_ready()
    assert error.value.reason is UnavailableReason.NOT_CONFIGURED


def test_check_ready_without_cached_token_is_not_logged_in(tmp_path):
    with pytest.raises(MusicUnavailable, match="audiohub music login") as error:
        auth_with(tmp_path / "token.json").check_ready()
    assert error.value.reason is UnavailableReason.NOT_LOGGED_IN


def test_access_token_comes_from_the_cache(spotify_auth):
    assert spotify_auth.access_token() == "cached-access-token"


def test_token_missing_a_scope_needs_a_new_login(tmp_path, make_token_cache):
    cache = make_token_cache(tmp_path / "token.json", scopes=SCOPES[:1])
    with pytest.raises(MusicUnavailable) as error:
        auth_with(cache).access_token()
    assert error.value.reason is UnavailableReason.NOT_LOGGED_IN


def test_rejected_refresh_means_login_expired(tmp_path, monkeypatch, make_token_cache):
    cache = make_token_cache(tmp_path / "token.json", expires_in_s=0)
    monkeypatch.setattr(SpotifyPKCE, "refresh_access_token", raiser(SpotifyOauthError("revoked")))
    with pytest.raises(MusicUnavailable, match="expired") as error:
        auth_with(cache).access_token()
    assert error.value.reason is UnavailableReason.NOT_LOGGED_IN


def test_network_failure_during_refresh_is_request_failed(tmp_path, monkeypatch, make_token_cache):
    cache = make_token_cache(tmp_path / "token.json", expires_in_s=0)
    monkeypatch.setattr(SpotifyPKCE, "refresh_access_token", raiser(OSError("offline")))
    with pytest.raises(MusicUnavailable, match="couldn't reach Spotify") as error:
        auth_with(cache).access_token()
    assert error.value.reason is UnavailableReason.REQUEST_FAILED


def test_login_always_asks_spotify_and_creates_the_cache_folder(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(
        SpotifyPKCE, "get_access_token", lambda self, check_cache: calls.append(check_cache)
    )
    cache = tmp_path / "new" / "token.json"
    assert auth_with(cache).login() == cache
    assert calls == [False]
    assert cache.parent.is_dir()


def test_failed_login_is_reported(tmp_path, monkeypatch):
    error_to_raise = SpotifyOauthError("access_denied")
    monkeypatch.setattr(SpotifyPKCE, "get_access_token", raiser(error_to_raise))
    with pytest.raises(MusicUnavailable, match="didn't complete: access_denied"):
        auth_with(tmp_path / "token.json").login()


def test_auth_manager_uses_pkce_with_the_playback_scopes(tmp_path):
    manager = build_auth_manager("abc123", "http://127.0.0.1:8888/callback", tmp_path / "t.json")
    assert isinstance(manager, SpotifyPKCE)
    assert manager.client_id == "abc123"
    assert manager.redirect_uri == "http://127.0.0.1:8888/callback"
    assert set(manager.scope.split()) == set(SCOPES)
    assert manager.cache_handler.cache_path == str(tmp_path / "t.json")
