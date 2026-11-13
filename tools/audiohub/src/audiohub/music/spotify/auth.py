"""Spotify login state: the client ID, the PKCE auth manager, and the cached token.

PKCE needs only a client ID (env SPOTIPY_CLIENT_ID), so no client secret is
stored anywhere. The token is cached in tools/audiohub/.cache/ (gitignored)
and refreshed automatically.

Only `login()` may start spotipy's interactive login (browser + local
redirect server). Everything else reads the cached token and raises
MusicUnavailable instead, because in the hub and the MCP server nobody is at a
prompt, and in the MCP server stdin is the protocol channel.
"""

import os
from collections.abc import Mapping
from pathlib import Path

from spotipy.cache_handler import CacheFileHandler
from spotipy.exceptions import SpotifyOauthError
from spotipy.oauth2 import SpotifyPKCE

from audiohub.config import CACHE_DIR, MusicSettings
from audiohub.music.errors import MusicUnavailable, UnavailableReason
from audiohub.music.spotify import messages

CLIENT_ID_ENV_VAR = "SPOTIPY_CLIENT_ID"

# The narrowest scopes covering playback control, playback state and the queue.
SCOPES: tuple[str, ...] = (
    "user-modify-playback-state",
    "user-read-playback-state",
    "user-read-currently-playing",
)

TOKEN_CACHE_PATH: Path = CACHE_DIR / "spotify-token.json"

# Seconds to wait on Spotify's token endpoint.
TOKEN_REQUEST_TIMEOUT_S = 10


class SpotifyAuth:
    """Hands out Spotify access tokens from the cache, and runs the one-time login.

    Args:
        music_settings: Supplies the OAuth redirect URI.
        environ: Where to read SPOTIPY_CLIENT_ID (default: os.environ).
        cache_path: The token cache file (default: TOKEN_CACHE_PATH).
    """

    def __init__(
        self,
        music_settings: MusicSettings,
        *,
        environ: Mapping[str, str] | None = None,
        cache_path: Path = TOKEN_CACHE_PATH,
    ) -> None:
        self.cache_path = cache_path
        self._redirect_uri = music_settings.redirect_uri
        self._environ = os.environ if environ is None else environ
        self._manager: SpotifyPKCE | None = None

    def check_ready(self) -> None:
        """Check, without any network call, that a client ID is set and a token is cached.

        Raises:
            MusicUnavailable: NOT_CONFIGURED or NOT_LOGGED_IN.
        """
        manager = self._auth_manager()
        if manager.cache_handler.get_cached_token() is None:
            raise MusicUnavailable(messages.NOT_LOGGED_IN, UnavailableReason.NOT_LOGGED_IN)

    def access_token(self) -> str:
        """Return a valid access token, refreshing it first if it's about to expire.

        Blocking: a refresh is a network call, so call this from an executor.

        Raises:
            MusicUnavailable: NOT_CONFIGURED, NOT_LOGGED_IN (no token, scopes
                changed, or the refresh was rejected) or REQUEST_FAILED
                (Spotify unreachable).
        """
        manager = self._auth_manager()
        try:
            token_info = manager.validate_token(manager.cache_handler.get_cached_token())
        except SpotifyOauthError as error:
            reason = UnavailableReason.NOT_LOGGED_IN
            raise MusicUnavailable(messages.LOGIN_EXPIRED, reason) from error
        except OSError as error:
            # requests' exceptions subclass OSError, so this covers network failures.
            reason = UnavailableReason.REQUEST_FAILED
            raise MusicUnavailable(messages.UNREACHABLE, reason) from error
        if token_info is None:
            raise MusicUnavailable(messages.NOT_LOGGED_IN, UnavailableReason.NOT_LOGGED_IN)
        return token_info["access_token"]

    def login(self) -> Path:
        """Run the interactive PKCE login and cache the token, even if one is cached already.

        Opens the browser on Spotify's consent page and blocks until Spotify
        redirects back to the loopback redirect URI.

        Returns:
            The token cache path.

        Raises:
            MusicUnavailable: NOT_CONFIGURED, or NOT_LOGGED_IN if the login
                failed (consent denied, redirect port busy, network error).
        """
        manager = self._auth_manager()
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            manager.get_access_token(check_cache=False)
        except (SpotifyOauthError, OSError) as error:
            message = messages.login_failed(str(error))
            raise MusicUnavailable(message, UnavailableReason.NOT_LOGGED_IN) from error
        return self.cache_path

    def _auth_manager(self) -> SpotifyPKCE:
        if self._manager is None:
            client_id = read_client_id(self._environ)
            self._manager = build_auth_manager(client_id, self._redirect_uri, self.cache_path)
        return self._manager


def read_client_id(environ: Mapping[str, str]) -> str:
    """Return the Spotify client ID from SPOTIPY_CLIENT_ID, stripped.

    Raises:
        MusicUnavailable: NOT_CONFIGURED if it's unset or blank.
    """
    client_id = environ.get(CLIENT_ID_ENV_VAR, "").strip()
    if not client_id:
        raise MusicUnavailable(messages.NOT_CONFIGURED, UnavailableReason.NOT_CONFIGURED)
    return client_id


def build_auth_manager(client_id: str, redirect_uri: str, cache_path: Path) -> SpotifyPKCE:
    """Build spotipy's PKCE auth manager with a file token cache.

    Args:
        client_id: The Spotify developer app's client ID.
        redirect_uri: Must match the app's registered redirect URI exactly.
        cache_path: The token cache file. Its folder is created on login.
    """
    return SpotifyPKCE(
        client_id=client_id,
        redirect_uri=redirect_uri,
        scope=list(SCOPES),
        cache_handler=CacheFileHandler(cache_path=str(cache_path)),
        requests_timeout=TOKEN_REQUEST_TIMEOUT_S,
        open_browser=True,
    )
