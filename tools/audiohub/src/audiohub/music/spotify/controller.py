"""`SpotifyController`: the MusicController backed by the Spotify Web API (via spotipy).

Needs Spotify Premium, SPOTIPY_CLIENT_ID, a one-time `audiohub music login`,
and an open Spotify app. If the app is open but idle (no active device),
player commands are retried on that device so it wakes up.
"""

import asyncio
import logging
import socket
from collections.abc import Callable
from pathlib import Path
from typing import Any

from audiohub.config import MusicSettings
from audiohub.music.arguments import check_query, check_search_kind, check_volume_percent
from audiohub.music.controller import SearchKind
from audiohub.music.errors import MusicUnavailable, UnavailableReason
from audiohub.music.now_playing import NowPlaying
from audiohub.music.spotify import messages
from audiohub.music.spotify.auth import SpotifyAuth
from audiohub.music.spotify.client import SpotifyApi, SpotifyCaller, create_spotify_api
from audiohub.music.spotify.devices import pick_device_id
from audiohub.music.spotify.items import SearchMatch, first_match, liked_songs_uri
from audiohub.music.spotify.playback import parse_playback

logger = logging.getLogger(__name__)

# Dev-mode apps get at most 10 search results per call (default 5). Only the
# first playable one is used; 5 leaves room to skip null playlist entries.
SEARCH_LIMIT = 5

# After a pause, Spotify's playback state can lag a moment. Re-read it up to
# this many times, this many seconds apart, before calling the pause ignored.
PAUSE_CHECK_ATTEMPTS = 3
PAUSE_CHECK_DELAY_S = 0.4

# Speakable name of the user's saved-tracks collection.
LIKED_SONGS = "your Liked Songs"

# A player command, given the spotipy client and a device id (None = the active one).
PlayerCommand = Callable[[SpotifyApi, str | None], Any]


class SpotifyController:
    """Controls the logged-in account's active (or else idle) Spotify Connect device.

    Every method may raise MusicUnavailable (see `UnavailableReason`) with a
    speakable message. No method ever opens a browser except `login()`.

    Args:
        music_settings: Supplies the OAuth redirect URI.
        auth: Token provider (default: SpotifyAuth over the real token cache).
        api: spotipy client (default: a real one). Tests pass fakes for both.
    """

    def __init__(
        self,
        music_settings: MusicSettings,
        *,
        auth: SpotifyAuth | None = None,
        api: SpotifyApi | None = None,
    ) -> None:
        self._auth = auth if auth is not None else SpotifyAuth(music_settings)
        self._caller = SpotifyCaller(self._auth, api if api is not None else create_spotify_api())

    def check_ready(self) -> None:
        """Check, without network calls, that Spotify is configured and logged in.

        Raises:
            MusicUnavailable: NOT_CONFIGURED or NOT_LOGGED_IN.
        """
        self._auth.check_ready()

    def login(self) -> Path:
        """Run the one-time interactive browser login. Blocking.

        Returns:
            Where the token was cached.

        Raises:
            MusicUnavailable: NOT_CONFIGURED, or NOT_LOGGED_IN if login failed.
        """
        return self._auth.login()

    async def play(self) -> None:
        """Resume playback, waking an idle device if none is active."""
        await self._player_command(lambda api, device: api.start_playback(device_id=device))

    async def pause(self) -> None:
        """Pause playback, then confirm Spotify stopped. Music already paused counts as paused.

        Spotify refuses to pause a paused player ("Restriction violated"), and
        the hub pauses the music itself while the user talks with Claude, so
        that refusal counts as success once the playback state reads paused.
        That expected refusal is logged at DEBUG; one that leaves music playing
        is logged at WARNING.

        Raises:
            MusicUnavailable: RESTRICTED if Spotify refused the pause and still
                reports music playing; REQUEST_FAILED if it accepted the pause
                but still reports music playing after a short wait.
        """
        try:
            await self._player_command(
                lambda api, device: api.pause_playback(device_id=device), refusal_expected=True
            )
        except MusicUnavailable as error:
            if error.reason is not UnavailableReason.RESTRICTED:
                raise
            # The confirm reads also wait out a state lagging behind a pause just made.
            if await self._is_still_playing():
                # The refusal itself was logged at DEBUG, as routine; this one isn't.
                logger.warning("Spotify refused to pause and still reports music playing")
                raise
            return
        if await self._is_still_playing():
            raise MusicUnavailable(messages.pause_ignored(), UnavailableReason.REQUEST_FAILED)

    async def toggle(self) -> None:
        """Pause if playing (a track, episode or ad), otherwise resume."""
        playback = await self._caller.call(lambda api: api.current_playback())
        # Read is_playing directly: parse_playback has no track for episodes/ads.
        if playback is not None and playback.get("is_playing"):
            await self.pause()
        else:
            await self.play()

    async def next(self) -> None:
        """Skip to the next track."""
        await self._player_command(lambda api, device: api.next_track(device_id=device))

    async def previous(self) -> None:
        """Go back to the previous track."""
        await self._player_command(lambda api, device: api.previous_track(device_id=device))

    async def now_playing(self) -> NowPlaying | None:
        """Return the active device's current track, or None if it has nothing loaded.

        Raises:
            MusicUnavailable: NO_ACTIVE_DEVICE when no device is active.
        """
        playback = await self._caller.call(lambda api: api.current_playback())
        if playback is None:
            raise MusicUnavailable(messages.NO_ACTIVE_DEVICE, UnavailableReason.NO_ACTIVE_DEVICE)
        return parse_playback(playback)

    async def set_volume(self, percent: int) -> None:
        """Set the device's volume, 0 to 100.

        Raises:
            ValueError: If `percent` is outside 0-100.
        """
        checked = check_volume_percent(percent)
        await self._player_command(lambda api, device: api.volume(checked, device_id=device))

    async def search_and_play(self, query: str, kind: SearchKind = "track") -> str:
        """Search Spotify and play the first match: one track, or an album/playlist/artist context.

        Returns:
            What started, e.g. "Babydoll by Dominic Fike".

        Raises:
            ValueError: If `query` is blank or `kind` isn't a SearchKind.
            MusicUnavailable: NOT_FOUND if nothing matched, or any API problem.
        """
        match = await self._find(query, kind)
        if match.kind == "track":
            target: dict[str, Any] = {"uris": [match.uri]}
        else:
            target = {"context_uri": match.uri}
        await self._player_command(
            lambda api, device: api.start_playback(device_id=device, **target)
        )
        return match.description

    async def play_liked(self, shuffle: bool | None = None) -> str:
        """Play the user's Liked Songs (their saved tracks) as a context.

        Args:
            shuffle: True or False sets the device's shuffle first; None leaves it.

        Returns:
            What started, e.g. "your Liked Songs on shuffle".

        Raises:
            MusicUnavailable: REQUEST_FAILED if `GET /me` has no user id, or any API problem.
        """
        profile = await self._caller.call(lambda api: api.current_user())
        context_uri = liked_songs_uri(profile if isinstance(profile, dict) else {})
        if context_uri is None:
            raise MusicUnavailable(messages.NO_USER_ID, UnavailableReason.REQUEST_FAILED)

        def shuffle_and_start(api: SpotifyApi, device: str | None) -> None:
            # Shuffle before starting, so the new context starts shuffled.
            if shuffle is not None:
                api.shuffle(shuffle, device_id=device)
            api.start_playback(device_id=device, context_uri=context_uri)

        await self._player_command(shuffle_and_start)
        return LIKED_SONGS + (" on shuffle" if shuffle else "")

    async def queue(self, query: str) -> str:
        """Search for a track and add the first match to the play queue.

        Returns:
            What was queued, e.g. "Babydoll by Dominic Fike".

        Raises:
            ValueError: If `query` is blank.
            MusicUnavailable: NOT_FOUND if nothing matched, or any API problem.
        """
        match = await self._find(query, "track")
        await self._player_command(
            lambda api, device: api.add_to_queue(match.uri, device_id=device)
        )
        return match.description

    async def _is_still_playing(self) -> bool:
        # Poll, since the state read right after a pause can still say playing.
        for attempt in range(PAUSE_CHECK_ATTEMPTS):
            playback = await self._caller.call(lambda api: api.current_playback())
            if playback is None or not playback.get("is_playing"):
                return False
            if attempt < PAUSE_CHECK_ATTEMPTS - 1:
                await asyncio.sleep(PAUSE_CHECK_DELAY_S)
        return True

    async def _player_command(
        self, command: PlayerCommand, *, refusal_expected: bool = False
    ) -> None:
        # Try the active device first; on NO_ACTIVE_DEVICE, retry on an idle one.
        # refusal_expected: see SpotifyCaller.call.
        try:
            await self._caller.call(
                lambda api: command(api, None), refusal_expected=refusal_expected
            )
        except MusicUnavailable as error:
            if error.reason is not UnavailableReason.NO_ACTIVE_DEVICE:
                raise
            await self._retry_on_idle_device(command, error, refusal_expected)

    async def _retry_on_idle_device(
        self, command: PlayerCommand, no_device_error: MusicUnavailable, refusal_expected: bool
    ) -> None:
        device_id = await self._caller.call(
            lambda api: pick_device_id(api.devices(), socket.gethostname())
        )
        if device_id is None:
            # Nothing to wake (the app is closed): keep the original error.
            raise no_device_error

        # Make the idle device the active one first: a bare start_playback
        # (resume) on an idle device still fails with NO_ACTIVE_DEVICE.
        def wake_and_run(api: SpotifyApi) -> Any:
            api.transfer_playback(device_id, force_play=False)
            return command(api, device_id)

        await self._caller.call(wake_and_run, refusal_expected=refusal_expected)

    async def _find(self, query: str, kind: str) -> SearchMatch:
        checked_query = check_query(query)
        checked_kind = check_search_kind(kind)
        results = await self._caller.call(
            # No market: "from_token" needs the user-read-private scope we don't request.
            lambda api: api.search(q=checked_query, limit=SEARCH_LIMIT, type=checked_kind)
        )
        match = first_match(results, checked_kind, checked_query)
        if match is None:
            message = messages.nothing_found(checked_kind, checked_query)
            raise MusicUnavailable(message, UnavailableReason.NOT_FOUND)
        return match
