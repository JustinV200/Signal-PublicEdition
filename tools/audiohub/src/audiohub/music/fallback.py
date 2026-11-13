"""`FallbackController`: try the primary backend, drop to the fallback for transport controls.

With backend "auto" the primary is Spotify and the fallback is the Windows
media session. Play/pause/toggle/skip/now-playing fall back only when the
primary can't be used at all (see FALLBACK_REASONS), so pause and
now-playing always read the same backend. Volume, search, Liked Songs
and queue only exist on the primary, so they always go there and report its error
(e.g. the Premium message).
"""

import logging
from collections.abc import Awaitable, Callable

from audiohub.music.controller import MusicController, SearchKind
from audiohub.music.errors import MusicUnavailable, UnavailableReason
from audiohub.music.now_playing import NowPlaying

logger = logging.getLogger(__name__)

# Primary failures that mean "this backend can't be used at all right now", as
# opposed to "it was asked and said no" (rate limit, nothing found, a player
# restriction, Premium required), which is reported. PREMIUM_REQUIRED is
# deliberately absent: only player commands need Premium, reading the current
# track doesn't, so falling back on it sent pause to the Windows media session
# while now-playing still read Spotify, and the two disagreed.
FALLBACK_REASONS: frozenset[UnavailableReason] = frozenset(
    {
        UnavailableReason.NOT_CONFIGURED,
        UnavailableReason.NOT_LOGGED_IN,
        UnavailableReason.NO_ACTIVE_DEVICE,
    }
)


class FallbackController:
    """A MusicController that prefers `primary` and falls back to `fallback`.

    Args:
        primary: Tried first for every command (normally SpotifyController).
        fallback: Used for transport controls when the primary raises
            MusicUnavailable with a reason in FALLBACK_REASONS (normally
            SmtcController). Its own errors propagate.
    """

    def __init__(self, primary: MusicController, fallback: MusicController) -> None:
        self._primary = primary
        self._fallback = fallback

    async def play(self) -> None:
        """Resume playback."""
        await self._transport(lambda controller: controller.play())

    async def pause(self) -> None:
        """Pause playback."""
        await self._transport(lambda controller: controller.pause())

    async def toggle(self) -> None:
        """Pause if playing, otherwise resume."""
        await self._transport(lambda controller: controller.toggle())

    async def next(self) -> None:
        """Skip to the next track."""
        await self._transport(lambda controller: controller.next())

    async def previous(self) -> None:
        """Go back to the previous track."""
        await self._transport(lambda controller: controller.previous())

    async def now_playing(self) -> NowPlaying | None:
        """Return the current track from whichever backend can be used."""
        return await self._transport(lambda controller: controller.now_playing())

    async def set_volume(self, percent: int) -> None:
        """Set the volume through the primary only."""
        await self._primary.set_volume(percent)

    async def search_and_play(self, query: str, kind: SearchKind = "track") -> str:
        """Search and play through the primary only."""
        return await self._primary.search_and_play(query, kind)

    async def play_liked(self, shuffle: bool | None = None) -> str:
        """Play the user's Liked Songs through the primary only."""
        return await self._primary.play_liked(shuffle)

    async def queue(self, query: str) -> str:
        """Queue a track through the primary only."""
        return await self._primary.queue(query)

    async def _transport[T](self, command: Callable[[MusicController], Awaitable[T]]) -> T:
        try:
            return await command(self._primary)
        except MusicUnavailable as error:
            if error.reason not in FALLBACK_REASONS:
                raise
            logger.info("primary music backend unusable (%s); using the fallback", error.reason)
        return await command(self._fallback)
