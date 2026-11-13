"""The `MusicController` protocol every music backend implements, plus the search kinds.

Callers (CLI, MCP tools, the voice loop) depend on this protocol only, so the
backend can be Spotify, the Windows media session, or a fallback pair of both.
"""

from typing import Literal, Protocol

from audiohub.music.now_playing import NowPlaying

SearchKind = Literal["track", "album", "playlist", "artist"]

# Every SearchKind value, in the order the CLI lists them.
SEARCH_KINDS: tuple[SearchKind, ...] = ("track", "album", "playlist", "artist")


class MusicController(Protocol):
    """Async music control. Every method may raise:

    - MusicUnavailable: the backend can't do it right now (not logged in, no
      active device, nothing playing, ...). The message is speakable.
    - UnsupportedOperation: the backend can never do it (e.g. search via SMTC).
    """

    async def play(self) -> None:
        """Resume playback."""
        ...

    async def pause(self) -> None:
        """Pause playback."""
        ...

    async def toggle(self) -> None:
        """Pause if playing, otherwise resume."""
        ...

    async def next(self) -> None:
        """Skip to the next track."""
        ...

    async def previous(self) -> None:
        """Go back to the previous track."""
        ...

    async def now_playing(self) -> NowPlaying | None:
        """Return the current track, or None if the player has nothing loaded."""
        ...

    async def set_volume(self, percent: int) -> None:
        """Set the player's volume, 0 to 100.

        Raises:
            ValueError: If `percent` is outside 0-100.
        """
        ...

    async def search_and_play(self, query: str, kind: SearchKind = "track") -> str:
        """Search for `query` and play the best match.

        Returns:
            A speakable description of what started, e.g. "Babydoll by Dominic Fike".

        Raises:
            ValueError: If `query` is blank or `kind` isn't a SearchKind.
        """
        ...

    async def play_liked(self, shuffle: bool | None = None) -> str:
        """Play the user's Liked Songs (their saved tracks), not a search result.

        Args:
            shuffle: True or False sets shuffle first; None leaves it as it is.

        Returns:
            A speakable description of what started, e.g. "your Liked Songs".
        """
        ...

    async def queue(self, query: str) -> str:
        """Search for a track and add it to the play queue.

        Returns:
            A speakable description of what was queued.

        Raises:
            ValueError: If `query` is blank.
        """
        ...
