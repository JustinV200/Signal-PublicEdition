"""Run spotipy calls off the event loop, each with a fresh token and speakable errors.

spotipy is synchronous, so every call runs in the default executor. Calls are
serialised with a lock because they share one spotipy client (and its
requests session), and the token is set on it just before each call.
"""

import asyncio
import threading
from collections.abc import Callable
from contextlib import nullcontext
from typing import Any, Protocol

import spotipy
from spotipy.exceptions import SpotifyException

from audiohub.music.errors import MusicUnavailable, UnavailableReason
from audiohub.music.spotify import messages
from audiohub.music.spotify.errors import (
    HTTP_TOO_MANY_REQUESTS,
    spotipy_refusal_log_dropped,
    to_music_unavailable,
)

# Seconds to wait on any one Web API request.
API_REQUEST_TIMEOUT_S = 10


class TokenSource(Protocol):
    """Anything that hands out Spotify access tokens (SpotifyAuth, or a test fake)."""

    def access_token(self) -> str:
        """Return a valid access token, or raise MusicUnavailable."""
        ...


class SpotifyApi(Protocol):
    """The part of `spotipy.Spotify` the music controller uses.

    A `device_id` of None means "the active device".
    """

    def set_auth(self, auth: str) -> None: ...
    def start_playback(self, device_id: str | None = None, **kwargs: Any) -> Any: ...
    def pause_playback(self, device_id: str | None = None) -> Any: ...
    def next_track(self, device_id: str | None = None) -> Any: ...
    def previous_track(self, device_id: str | None = None) -> Any: ...
    def volume(self, volume_percent: int, device_id: str | None = None) -> Any: ...
    def current_playback(self) -> dict[str, Any] | None: ...
    def transfer_playback(self, device_id: str, force_play: bool = True) -> Any: ...
    def devices(self) -> dict[str, Any] | None: ...
    def search(self, q: str, limit: int, type: str) -> dict[str, Any]: ...
    def add_to_queue(self, uri: str, device_id: str | None = None) -> Any: ...
    def shuffle(self, state: bool, device_id: str | None = None) -> Any: ...
    def current_user(self) -> dict[str, Any]: ...


def create_spotify_api() -> SpotifyApi:
    """Build the real spotipy client, authorised per call through `set_auth`.

    Status retries are off on purpose: urllib3 honours Spotify's Retry-After
    header, which can be hours when a dev-mode quota is exceeded, and would
    block the call that long. A 429 is reported to the user straight away.
    Only 429 is listed so that 5xx errors keep their real status code.
    """
    return spotipy.Spotify(
        requests_timeout=API_REQUEST_TIMEOUT_S,
        status_retries=0,
        status_forcelist=(HTTP_TOO_MANY_REQUESTS,),
    )


class SpotifyCaller:
    """Runs one spotipy operation at a time on an executor thread.

    Args:
        auth: Supplies the access token for each call.
        api: The spotipy client (or a fake in tests).
    """

    def __init__(self, auth: TokenSource, api: SpotifyApi) -> None:
        self._auth = auth
        self._api = api
        self._lock = threading.Lock()

    async def call[T](
        self, operation: Callable[[SpotifyApi], T], *, refusal_expected: bool = False
    ) -> T:
        """Run `operation(api)` in the default executor and return its result.

        Args:
            operation: The spotipy call to make.
            refusal_expected: The caller expects Spotify may refuse with
                "Restriction violated" and checks the outcome itself, so that
                refusal is logged at DEBUG (see `spotify.errors`).

        Raises:
            MusicUnavailable: Not configured or logged in, any Spotify HTTP
                error (mapped to a speakable message), or Spotify unreachable.
        """
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._call_blocking, operation, refusal_expected)

    def _call_blocking[T](self, operation: Callable[[SpotifyApi], T], refusal_expected: bool) -> T:
        with self._lock:
            self._api.set_auth(self._auth.access_token())
            # spotipy logs the refusal from inside the call, on this thread.
            quieted = spotipy_refusal_log_dropped() if refusal_expected else nullcontext()
            try:
                with quieted:
                    return operation(self._api)
            except SpotifyException as error:
                raise to_music_unavailable(error, refusal_expected=refusal_expected) from error
            except OSError as error:
                # requests' exceptions (timeouts, DNS, refused) subclass OSError.
                raise MusicUnavailable(
                    messages.UNREACHABLE, UnavailableReason.REQUEST_FAILED
                ) from error
