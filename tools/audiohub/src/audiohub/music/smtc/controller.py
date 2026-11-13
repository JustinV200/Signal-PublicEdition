"""`SmtcController`: the MusicController backed by the Windows media session (SMTC).

Works with any app that shows in the Windows media flyout (Spotify, browsers,
...), with no login, Premium or network. It can only play, pause, skip and
report the current track; volume, search and queue raise UnsupportedOperation.
"""

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

from audiohub.music.controller import SearchKind
from audiohub.music.errors import MusicUnavailable, UnavailableReason, UnsupportedOperation
from audiohub.music.now_playing import SMTC_SOURCE_PREFIX, NowPlaying
from audiohub.music.smtc.manager import (
    MediaSession,
    SessionManager,
    request_session_manager,
    winrt_errors_as_unavailable,
)
from audiohub.music.smtc.sessions import pick_session

# GlobalSystemMediaTransportControlsSessionPlaybackStatus values. The winrt
# enum is an IntEnum, so it compares equal to these.
STOPPED_STATUS = 3
PLAYING_STATUS = 4
PAUSED_STATUS = 5
# Statuses where a pause has nothing to do. CLOSED (0), OPENED (1), CHANGING
# (2, mid track change) and an unknown status still get the pause, or it could
# be lost.
NOTHING_TO_PAUSE_STATUSES = frozenset({STOPPED_STATUS, PAUSED_STATUS})

# Windows updates a session's status a moment after accepting a pause. Re-read
# it up to this many times, this many seconds apart, before calling it ignored.
PAUSE_CHECK_ATTEMPTS = 3
PAUSE_CHECK_DELAY_S = 0.3

NO_SESSION_MESSAGE = "Nothing on this PC is playing media; open the Spotify app"
VOLUME_UNSUPPORTED_MESSAGE = "I can't set the volume through the Windows media controls."
SEARCH_UNSUPPORTED_MESSAGE = "I can't search for music through the Windows media controls."
QUEUE_UNSUPPORTED_MESSAGE = "I can't queue music through the Windows media controls."


class SmtcController:
    """Controls Spotify's Windows media session if it has one, else the current session.

    Args:
        request_manager: Returns the session manager (default: the real winrt
            one). Tests pass a fake.
    """

    def __init__(
        self, request_manager: Callable[[], Awaitable[SessionManager]] = request_session_manager
    ) -> None:
        self._request_manager = request_manager

    async def play(self) -> None:
        """Resume playback. Raises MusicUnavailable if no session or the app refuses."""
        await self._command("play", lambda session: session.try_play_async())

    async def pause(self) -> None:
        """Pause playback. Music already paused (or stopped) counts as paused.

        Some apps refuse to pause twice, and the hub pauses the music itself
        while the user talks with Claude.

        Raises:
            MusicUnavailable: No session, the app refuses, or it accepts the
                pause but still reports PLAYING afterwards.
        """
        session = await self._require_session()
        if _playback_status(session) in NOTHING_TO_PAUSE_STATUSES:
            return
        await self._send(session, "pause", lambda session: session.try_pause_async())
        if await self._is_still_playing(session):
            message = f"{session.source_app_user_model_id} accepted the pause but is still playing."
            raise MusicUnavailable(message, UnavailableReason.REQUEST_FAILED)

    async def toggle(self) -> None:
        """Toggle play/pause. Raises MusicUnavailable if no session or the app refuses."""
        await self._command("play or pause", lambda session: session.try_toggle_play_pause_async())

    async def next(self) -> None:
        """Skip to the next track. Raises MusicUnavailable if no session or the app refuses."""
        await self._command("skip", lambda session: session.try_skip_next_async())

    async def previous(self) -> None:
        """Go back a track. Raises MusicUnavailable if no session or the app refuses."""
        await self._command("go back", lambda session: session.try_skip_previous_async())

    async def now_playing(self) -> NowPlaying | None:
        """Return the session's current media, or None if there's no session or no media.

        Raises:
            MusicUnavailable: REQUEST_FAILED if Windows fails the request.
        """
        session = await self._session()
        if session is None:
            return None
        with winrt_errors_as_unavailable():
            properties = await session.try_get_media_properties_async()
        if properties is None:
            return None
        return NowPlaying(
            title=properties.title or "",
            artist=properties.artist or "",
            album=properties.album_title or "",
            is_playing=_is_playing(session),
            source=SMTC_SOURCE_PREFIX + session.source_app_user_model_id,
        )

    async def set_volume(self, percent: int) -> None:
        """Always raises UnsupportedOperation; SMTC has no volume control."""
        raise UnsupportedOperation(VOLUME_UNSUPPORTED_MESSAGE)

    async def search_and_play(self, query: str, kind: SearchKind = "track") -> str:
        """Always raises UnsupportedOperation; SMTC can't choose what plays."""
        raise UnsupportedOperation(SEARCH_UNSUPPORTED_MESSAGE)

    async def play_liked(self, shuffle: bool | None = None) -> str:
        """Always raises UnsupportedOperation; SMTC can't choose what plays."""
        raise UnsupportedOperation(SEARCH_UNSUPPORTED_MESSAGE)

    async def queue(self, query: str) -> str:
        """Always raises UnsupportedOperation; SMTC can't see the queue."""
        raise UnsupportedOperation(QUEUE_UNSUPPORTED_MESSAGE)

    async def _session(self) -> MediaSession | None:
        manager = await self._request_manager()
        with winrt_errors_as_unavailable():
            return pick_session(manager)

    async def _is_still_playing(self, session: MediaSession) -> bool:
        for attempt in range(PAUSE_CHECK_ATTEMPTS):
            if not _is_playing(session):
                return False
            if attempt < PAUSE_CHECK_ATTEMPTS - 1:
                await asyncio.sleep(PAUSE_CHECK_DELAY_S)
        return True

    async def _command(self, action: str, send: Callable[[MediaSession], Any]) -> None:
        await self._send(await self._require_session(), action, send)

    async def _require_session(self) -> MediaSession:
        session = await self._session()
        if session is None:
            raise MusicUnavailable(NO_SESSION_MESSAGE, UnavailableReason.NO_SESSION)
        return session

    async def _send(
        self, session: MediaSession, action: str, send: Callable[[MediaSession], Any]
    ) -> None:
        message = f"{session.source_app_user_model_id} didn't respond to {action}."
        # A failed HRESULT raises OSError; an ignored command resolves to False.
        with winrt_errors_as_unavailable(message):
            accepted = await send(session)
        if not accepted:
            raise MusicUnavailable(message, UnavailableReason.REQUEST_FAILED)


def _playback_status(session: MediaSession) -> int | None:
    """The session's playback status right now, or None if Windows reports none.

    Raises:
        MusicUnavailable: REQUEST_FAILED if Windows fails the request.
    """
    with winrt_errors_as_unavailable():
        info = session.get_playback_info()
    return None if info is None else info.playback_status


def _is_playing(session: MediaSession) -> bool:
    return _playback_status(session) == PLAYING_STATUS
