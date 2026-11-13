"""`MusicPause`: pause the music while the user talks with Claude, then resume it.

A session starts when the hub hears its wake phrase (`hold()`, from the
conversation) or starts speaking (a notification, say). If music is playing
then, it is paused, and remembered as paused by us. The session lasts while
Claude is thinking or speaking and, once the user has spoken, while the
follow-up window is open or messages wait to be spoken. `resume_after_s`
after all that ends, the music is resumed, but only if it is still paused on
the same track and Claude wasn't asked to play or pause it meanwhile
(`note_tool_call`). After Claude skipped a track, whatever is paused is
resumed, so the new track plays. Music that wasn't playing is never started,
and music is paused at most once per session, so a track the user starts
mid-conversation keeps playing. Stopping the hub mid-session leaves the
music paused.

Music calls run in this task only, each capped at MUSIC_CALL_TIMEOUT_S, so a
slow or missing backend never delays hearing or speech; failures are logged.
The hub is polled, because the follow-up window ends by time alone, with no
event to wait for.
"""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Protocol

from audiohub.music import MusicController, MusicUnavailable, NowPlaying

logger = logging.getLogger(__name__)

# How often the hub's activity is checked, in seconds.
POLL_S = 0.1
# Longest wait for one music call. Spotify's pause re-reads the playback
# state for about a second to confirm it took. The cap only cuts awaits: the
# Windows media session's synchronous WinRT calls run on the event loop, and
# nothing can interrupt them.
MUSIC_CALL_TIMEOUT_S = 5.0
# How Claude Code names the audiohub MCP server's tools: mcp__<key>__<tool>,
# with the server's key in the repo root's .mcp.json (audiohub.mcp.SERVER_NAME
# matches it; tests/mcp/test_launch.py checks all three agree).
AUDIOHUB_TOOL_PREFIX = "mcp__audiohub__"
# The audiohub music tools (named in audiohub.mcp's app.py) that mean the user
# took charge of playback: after one, the music is left as it is.
PLAYBACK_TOOLS = frozenset(
    {"music_play", "music_pause", "music_search_and_play", "music_play_liked"}
)
# Tools that change the track: after one, whatever is paused is resumed.
SKIP_TOOLS = frozenset({"music_next", "music_previous"})

Sleep = Callable[[float], Awaitable[None]]


class HubActivity(Protocol):
    """What the music pause asks the hub, at the moment it asks."""

    def is_busy(self) -> bool:
        """Whether Claude is thinking or speaking."""
        ...

    def is_conversation_open(self) -> bool:
        """Whether the user may still reply without the wake phrase, or messages wait to be said."""
        ...


class MusicPause:
    """Pauses the music for the hub's conversations and speech. Run `run(hub)` as a task."""

    def __init__(
        self, music: MusicController, resume_after_s: float, *, sleep: Sleep = asyncio.sleep
    ) -> None:
        """Prepare the pause; nothing is checked or paused until `run()`.

        Args:
            music: The music backend, normally from `music.create_controller`.
            resume_after_s: How long the hub must stay idle before the music
                is resumed (`music.resume_after_s`).
            sleep: Waits between polls; tests pass one driven by a fake clock.
        """
        self._music = music
        self._resume_after_s = resume_after_s
        self._sleep = sleep
        self._is_hold_requested = False
        self._is_in_session = False
        # What Claude was asked to do to the music during this session.
        self._is_taken_over = False
        self._is_skipped = False

    def hold(self) -> None:
        """The user said the wake phrase or a request: pause soon, until the conversation ends.

        Returns at once; the music calls happen in `run()`.
        """
        self._is_hold_requested = True

    def note_tool_call(self, tool_name: str) -> None:
        """Hear about a tool call Claude is allowed to make (the brain's `on_tool_call`).

        Args:
            tool_name: E.g. "mcp__audiohub__music_pause". A play or pause
                command during a session leaves the music as the user wanted
                it; a skip makes the new track resume.
        """
        if not self._is_in_session or not tool_name.startswith(AUDIOHUB_TOOL_PREFIX):
            return
        tool = tool_name.removeprefix(AUDIOHUB_TOOL_PREFIX)
        if tool in PLAYBACK_TOOLS:
            self._is_taken_over = True
        elif tool in SKIP_TOOLS:
            self._is_skipped = True

    async def run(self, hub: HubActivity) -> None:
        """Pause and resume the music for each conversation, forever (until cancelled).

        Args:
            hub: Says whether Claude is busy and whether the conversation is open.
        """
        while True:
            while not (self._is_hold_requested or hub.is_busy()):
                await self._sleep(POLL_S)
            await self._run_session(hub)

    async def _run_session(self, hub: HubActivity) -> None:
        self._is_in_session, self._is_taken_over, self._is_skipped = True, False, False
        try:
            paused = await self._pause_if_playing()
            await self._wait_until_over(hub)
            if paused is not None:
                await self._resume_if_untouched(paused)
        finally:
            self._is_in_session = False

    async def _wait_until_over(self, hub: HubActivity) -> None:
        """Return once the hub has been idle for `resume_after_s`.

        The follow-up window and unsaid messages only count once the user has
        spoken (a `hold()`), so the music isn't kept paused after a notification
        on the chance that the user replies.
        """
        # Idle time is counted in whole polls, so summing floats can't drift.
        is_woken, idle_polls = False, 0
        while True:
            is_held, self._is_hold_requested = self._is_hold_requested, False
            is_woken = is_woken or is_held
            if is_held or hub.is_busy() or (is_woken and hub.is_conversation_open()):
                idle_polls = 0
            elif idle_polls * POLL_S >= self._resume_after_s:
                return
            else:
                idle_polls += 1
            await self._sleep(POLL_S)

    async def _pause_if_playing(self) -> NowPlaying | None:
        """Pause the music if it is playing.

        Returns:
            What was paused, or None if nothing was playing or the pause failed.
            A pause that timed out may still land later; it isn't claimed, so
            music the user paused is never resumed by mistake.
        """
        try:
            playing = await _within_timeout(self._music.now_playing())
            if playing is None or not playing.is_playing:
                return None
            await _within_timeout(self._music.pause())
        except Exception as error:
            # Broad on purpose: this task runs beside hearing and speech, so
            # a music failure must cost the pause only, never the hub.
            _log_failure("pause", error)
            return None
        logger.info("paused %s for Claude", playing.describe())
        return playing

    async def _resume_if_untouched(self, paused: NowPlaying) -> None:
        """Resume what was paused (or skipped to), unless the user changed the music meanwhile."""
        if self._is_taken_over:
            logger.info("not resuming the music: Claude was asked to play or pause it")
            return
        try:
            current = await _within_timeout(self._music.now_playing())
            if current is None or current.is_playing:
                logger.info("not resuming the music: it is playing again, or nothing is loaded")
                return
            if not _is_ours(current, paused, self._is_skipped):
                logger.info("not resuming the music: another track is loaded")
                return
            await _within_timeout(self._music.play())
        except Exception as error:
            # Broad on purpose, as in _pause_if_playing.
            _log_failure("resume", error)
            return
        logger.info("resumed %s", current.describe())


async def _within_timeout[T](call: Awaitable[T]) -> T:
    return await asyncio.wait_for(call, MUSIC_CALL_TIMEOUT_S)


def _is_ours(current: NowPlaying, paused: NowPlaying, is_skipped: bool) -> bool:
    """Whether the current track is the one paused for Claude, or one Claude skipped to."""
    # By title and artist, not the source: Spotify's Web API can lose a
    # long-paused device, and the Windows media session then reports the same
    # track for the same app.
    return is_skipped or (current.title, current.artist) == (paused.title, paused.artist)


def _log_failure(action: str, error: Exception) -> None:
    if isinstance(error, MusicUnavailable):
        # Expected, e.g. no music app is open: one line, no traceback.
        logger.info("could not %s the music: %s", action, error)
    elif isinstance(error, TimeoutError):
        logger.warning("could not %s the music: no answer in %s s", action, MUSIC_CALL_TIMEOUT_S)
    else:
        logger.warning("could not %s the music", action, exc_info=error)
