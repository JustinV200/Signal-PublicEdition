"""SessionKeeper: keeps the brain's one session open, with the voice pick and MCP servers current.

The console writes the owner's model and effort pick for voice to
brain-choice.json. ClaudeBrain calls prepare_turn() between turns, just before
it sends a request:

- a new model goes through the session's live set_model, no reconnect;
- a new effort, which the CLI only takes at start, or a changed .mcp.json
  (its servers are fixed for a session's life), closes the session and
  opens a new one that resumes the same conversation (its id comes from the
  last turn result). That costs one CLI startup on that turn;
- otherwise MCP servers the CLI reports as failed are reconnected (mcp_heal.py).

If that reconnect fails, that request fails, the keeper holds no session,
and the next request's prepare_turn() tries again. A failed resume also drops
the conversation id, so the retry starts a new conversation: a bad id can't
keep voice dead.

The reconnect stops the old CLI process, so background work started in it
(background agents, shells) is dropped; its results never arrive.
"""

import asyncio
import logging
from collections.abc import Callable, Coroutine
from pathlib import Path
from typing import Any

from audiohub.brain.connection.mcp_heal import McpHealer
from audiohub.brain.connection.protocol import BrainSession
from audiohub.config import BrainSettings, with_brain_choice

logger = logging.getLogger(__name__)

SessionBuilder = Callable[[BrainSettings], BrainSession]
EventReader = Callable[[BrainSession], Coroutine[Any, Any, None]]


class SessionKeeper:
    """Opens, swaps and closes the brain's session, and runs its one reader task."""

    # Five parameters, one over the usual limit: each is a separate input, and
    # bundling two paths into an options object would only move them.
    def __init__(
        self,
        settings: BrainSettings,
        choice_path: Path,
        mcp_config_path: Path,
        build_session: SessionBuilder,
        read_events: EventReader,
    ) -> None:
        """Prepare; nothing connects until start().

        Args:
            settings: The [brain] settings; the pick in `choice_path` goes on top.
            choice_path: brain-choice.json, read at start and by each prepare_turn().
            mcp_config_path: The repo's .mcp.json; a change to its mtime reconnects.
            build_session: Builds an unconnected session for the given settings.
            read_events: The reader each new session gets, run as its own task.
        """
        self._settings = settings
        self._choice_path = choice_path
        self._mcp_config_path = mcp_config_path
        self._mcp_config_mtime: float | None = None  # as the open session saw it
        self._healer = McpHealer()
        self._build_session = build_session
        self._read_events = read_events
        self._session: BrainSession | None = None
        self._reader: asyncio.Task[None] | None = None
        self._active = settings  # what the open session runs with
        self._resume_id: str | None = None
        self._is_started = False

    @property
    def session(self) -> BrainSession | None:
        """The open session, or None before start(), after close() or after a failed reconnect."""
        return self._session

    @property
    def is_reader_done(self) -> bool:
        """Whether the open session's reader has stopped (its stream ended or failed)."""
        return self._reader is not None and self._reader.done()

    async def start(self) -> None:
        """Open the session with the current pick. Does nothing if already started.

        Raises:
            claude_agent_sdk.ClaudeSDKError: The Claude CLI couldn't start.
        """
        if self._is_started:
            return
        await self._open(with_brain_choice(self._settings, self._choice_path))
        self._is_started = True

    async def close(self) -> None:
        """Stop the reader and disconnect. Safe to call more than once."""
        self._is_started = False
        await self._close_session()

    async def prepare_turn(self) -> None:
        """Apply the current pick and heal MCP servers; call only between turns.

        Raises:
            claude_agent_sdk.ClaudeSDKError: The reconnect or the model switch failed.
        """
        if not self._is_started:
            return  # the caller's own "not started" check reports it
        wanted = with_brain_choice(self._settings, self._choice_path)
        session = self._session
        reason = "session lost" if session is None else self._reconnect_reason(wanted)
        if session is None or reason is not None:
            logger.info("voice %s: reconnecting, resuming the conversation", reason)
            await self._close_session()
            await self._open(wanted)
            return  # the new session connects every MCP server afresh
        if wanted.model != self._active.model:
            logger.info("voice model now %s", wanted.model)
            await session.set_model(wanted.model)
            self._active = wanted
        await self._healer.heal(session)

    def _reconnect_reason(self, wanted: BrainSettings) -> str | None:
        """Why the open session must be reopened before this turn, or None if it needn't be."""
        if wanted.effort != self._active.effort:
            return f"effort {wanted.effort}"
        if _mtime(self._mcp_config_path) != self._mcp_config_mtime:
            return "MCP config changed"
        return None

    async def _open(self, settings: BrainSettings) -> None:
        # Read before connecting, so an edit made while the CLI starts reconnects next turn.
        config_mtime = _mtime(self._mcp_config_path)
        session = self._build_session(settings)
        try:
            await session.connect(self._resume_id)
        except Exception:
            if self._resume_id is not None:
                logger.warning("resuming %s failed; the next try starts afresh", self._resume_id)
                self._resume_id = None
            raise
        self._session, self._active = session, settings
        self._mcp_config_mtime = config_mtime
        self._reader = asyncio.create_task(self._read_events(session), name="claude-brain-reader")

    async def _close_session(self) -> None:
        if self._session is None:
            return
        session, self._session = self._session, None
        self._resume_id = session.session_id or self._resume_id
        reader, self._reader = self._reader, None
        if reader is not None:
            reader.cancel()
            # The reader catches its own errors, so waiting can't raise; its finally
            # block resets the router (ends any open turn, forgets injected state).
            await asyncio.wait({reader})
        await session.disconnect()


def _mtime(path: Path) -> float | None:
    """The file's modification time, or None when it can't be read (missing counts as a state)."""
    try:
        return path.stat().st_mtime
    except OSError:
        return None
