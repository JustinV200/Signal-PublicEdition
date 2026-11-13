"""The MCP `music_*` tools: thin wrappers over a `MusicController` that return speakable text.

Arguments are checked here with music's shared boundary checks; a bad one
(volume out of range, blank query) raises ToolError, so the model gets an
error result it can correct. MusicUnavailable / UnsupportedOperation carry a
speakable message (e.g. "open the Spotify app"), which becomes the text
result. Anything else propagates; the SDK logs it to stderr and reports a
tool error.
"""

import logging
from collections.abc import Awaitable, Callable

from mcp.server.mcpserver.exceptions import ToolError

from audiohub.music import (
    MusicController,
    MusicUnavailable,
    NowPlaying,
    SearchKind,
    UnsupportedOperation,
    check_query,
    check_search_kind,
    check_volume_percent,
)

logger = logging.getLogger(__name__)

MusicOperation = Callable[[MusicController], Awaitable[str]]

DEFAULT_SEARCH_KIND: SearchKind = "track"
NOTHING_PLAYING = "Nothing is playing right now."


class MusicTools:
    """Backs the music_* tools. Each method returns one sentence for the model.

    Args:
        controller: The music backend, normally from `music.create_controller`.
    """

    def __init__(self, controller: MusicController) -> None:
        self._controller = controller

    async def now_playing(self) -> str:
        """Describe the current track and whether it is playing or paused."""
        return await self._attempt(_describe_now_playing)

    async def play(self) -> str:
        """Resume playback."""
        return await self._attempt(lambda music: _then(music.play(), "Playing."))

    async def pause(self) -> str:
        """Pause playback."""
        return await self._attempt(lambda music: _then(music.pause(), "Paused."))

    async def next(self) -> str:
        """Skip to the next track."""
        return await self._attempt(lambda music: _then(music.next(), "Skipped to the next track."))

    async def previous(self) -> str:
        """Go back to the previous track."""
        confirmation = "Went back to the previous track."
        return await self._attempt(lambda music: _then(music.previous(), confirmation))

    async def set_volume(self, percent: int) -> str:
        """Set the player's volume to `percent` (0-100).

        Raises:
            ToolError: If `percent` isn't a whole number from 0 to 100.
        """
        checked = _checked(check_volume_percent, percent)
        confirmation = f"Volume set to {checked} percent."
        return await self._attempt(lambda music: _then(music.set_volume(checked), confirmation))

    async def search_and_play(self, query: str, kind: SearchKind = DEFAULT_SEARCH_KIND) -> str:
        """Search for `query` and play the best match of the given kind.

        Raises:
            ToolError: If `query` is blank or `kind` is unknown.
        """
        checked_query = _checked(check_query, query)
        checked_kind = _checked(check_search_kind, kind)

        async def operation(music: MusicController) -> str:
            return f"Now playing {await music.search_and_play(checked_query, checked_kind)}."

        return await self._attempt(operation)

    async def play_liked(self, shuffle: bool | None = None) -> str:
        """Play the user's Liked Songs, optionally setting shuffle on or off first."""

        async def operation(music: MusicController) -> str:
            return f"Now playing {await music.play_liked(shuffle)}."

        return await self._attempt(operation)

    async def queue(self, query: str) -> str:
        """Search for a track and add it to the play queue.

        Raises:
            ToolError: If `query` is blank.
        """
        checked_query = _checked(check_query, query)

        async def operation(music: MusicController) -> str:
            return f"Queued {await music.queue(checked_query)}."

        return await self._attempt(operation)

    async def _attempt(self, operation: MusicOperation) -> str:
        """Run `operation` on the controller; a music error becomes its speakable message."""
        try:
            return await operation(self._controller)
        except (MusicUnavailable, UnsupportedOperation) as error:
            logger.info("music tool could not run: %s", error)
            return str(error)


def format_now_playing(now: NowPlaying | None) -> str:
    """Turn a now-playing report into one sentence.

    Args:
        now: The controller's report, or None when nothing is loaded.

    Returns:
        e.g. "Playing: Babydoll by Dominic Fike, from the album Sunburn." or
        NOTHING_PLAYING.
    """
    if now is None:
        return NOTHING_PLAYING
    state = "Playing" if now.is_playing else "Paused"
    album = f", from the album {now.album}" if now.album else ""
    return f"{state}: {now.describe()}{album}."


def _checked[Arg, Checked](check: Callable[[Arg], Checked], value: Arg) -> Checked:
    """Run one of music's argument checks, turning its ValueError into a ToolError."""
    try:
        return check(value)
    except ValueError as error:
        raise ToolError(str(error)) from error


async def _describe_now_playing(music: MusicController) -> str:
    """Fetch and format the current track."""
    return format_now_playing(await music.now_playing())


async def _then(command: Awaitable[None], confirmation: str) -> str:
    """Await a command that returns nothing, then return its confirmation text."""
    await command
    return confirmation
