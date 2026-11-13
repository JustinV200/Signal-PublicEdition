"""ClaudeBrain: the voice loop's handle on one persistent, multi-turn Claude Code session.

The loop calls ask() with each transcribed request and gets ReplyText events
back (they go to the kernel), then a TurnDone. A single reader task, started
with the session, reads every session event and hands it to a TurnRouter.
Text from turns the CLI starts on its own goes to on_background_text instead,
and ask() waits for such a turn to end before sending. A turn that shows no
activity for `turn_stall_timeout_s` is given up on, so one lost result can't
wedge the voice loop. Every tool call goes through the PermissionGate, which
allows voice's own quick tools and refuses the rest quietly; allowed ones are
reported to on_tool_call. Each request
is also noted for the hand-off tool, which sends the owner's own words with a job it
passes to the main Signal session. Before each request, a SessionKeeper
(connection/keeper.py) applies the console's voice pick (brain-choice.json):
a new model live, a new effort by reconnecting with resume. It also reconnects
with resume when .mcp.json changes, and reconnects failed MCP servers. The session sits
behind the BrainSession protocol (connection/protocol.py); SdkSession is the
real one, and tests inject a fake.
"""

import asyncio
import logging
from collections.abc import AsyncIterator
from pathlib import Path
from types import TracebackType
from typing import Self

from audiohub.brain.connection import (
    BrainSession,
    SessionFactory,
    SessionKeeper,
    ToolCallHandler,
)
from audiohub.brain.events import ReplyText, TurnDone
from audiohub.brain.handoff_tool import MainSessionHandoff
from audiohub.brain.permissions import (
    PermissionDecision,
    PermissionGate,
    PermissionRequest,
)
from audiohub.brain.sdk_session import SdkSession
from audiohub.brain.turn_router import BackgroundTextHandler, TurnEvent, TurnRouter
from audiohub.brain.turn_watchdog import next_turn_event
from audiohub.config import BRAIN_CHOICE_PATH, ORCHESTRATOR_CLAIM_PATH, BrainSettings

logger = logging.getLogger(__name__)

# The repo's MCP server list, under cwd; the keeper reconnects when it changes.
MCP_CONFIG_FILE = ".mcp.json"


class ClaudeBrain:
    """One persistent Claude Code session that the user talks to by voice.

    Use it as an async context manager, or call start() and close(). ask() calls
    are serialised: a second one waits for the first turn to finish. interrupt()
    may be called from another task while ask() is being iterated.
    """

    # Seven parameters, three over the usual limit: the last five are optional,
    # keyword-only hooks (three test seams and two loop callbacks), not configuration.
    def __init__(
        self,
        brain_settings: BrainSettings,
        cwd: Path,
        *,
        session_factory: SessionFactory = SdkSession,
        on_background_text: BackgroundTextHandler | None = None,
        on_tool_call: ToolCallHandler | None = None,
        main_session: MainSessionHandoff | None = None,
        choice_path: Path = BRAIN_CHOICE_PATH,
    ) -> None:
        """Prepare the brain. Nothing starts until start().

        Args:
            brain_settings: Model and the permission gate's lists.
            cwd: Working directory for Claude Code, normally the repo root.
            session_factory: Builds the session; tests pass a fake.
            on_background_text: Gets text from turns Claude starts on its own (e.g.
                when a background agent finishes). It may be sync or async and
                should return quickly. None drops such text with a log line.
            on_tool_call: Told the name of each tool call the gate allows, just
                before it runs. It must return quickly; an error it raises is
                logged and the call still runs.
            main_session: The hand-off tool's sender, told each request sent.
                None reaches the orchestrator `console claim` recorded; tests
                pass one with their own claim file.
            choice_path: The console's voice pick (brain-choice.json); tests pass a tmp one.
        """
        self._settings = brain_settings
        self._cwd = cwd
        self._gate = PermissionGate(
            brain_settings.auto_allow_tools,
            cwd,
            auto_allow_mcp_servers=brain_settings.auto_allow_mcp_servers,
        )
        self._session_factory = session_factory
        self._on_tool_call = on_tool_call
        self._main_session = main_session or MainSessionHandoff(ORCHESTRATOR_CLAIM_PATH)
        self._router = TurnRouter(on_background_text)
        self._ask_lock = asyncio.Lock()
        self._keeper = SessionKeeper(
            brain_settings,
            choice_path,
            cwd / MCP_CONFIG_FILE,
            self._build_session,
            self._read_events,
        )
        self._session_error: Exception | None = None
        # Bumped by every interrupt(). An ask() still waiting for an earlier or
        # injected turn compares it before sending, so "stop" cancels it too.
        self._interrupt_count = 0

    async def start(self) -> None:
        """Connect the session and start reading it. Does nothing if already started.

        Raises:
            claude_agent_sdk.ClaudeSDKError: The Claude CLI couldn't start.
        """
        await self._keeper.start()

    async def close(self) -> None:
        """Stop reading and disconnect the session. Safe to call more than once."""
        await self._keeper.close()

    async def __aenter__(self) -> Self:
        """Start the brain for an `async with` block."""
        await self.start()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Close the brain when the `async with` block ends."""
        await self.close()

    async def ask(self, text: str) -> AsyncIterator[ReplyText | TurnDone]:
        """Send one request and stream Claude's reply.

        Iterate to the TurnDone, or close the iterator (e.g. `break`). An abandoned
        turn keeps running in Claude, and the next ask() waits for it to finish.
        So does a turn Claude started on its own: a request sent into it would
        never get a result of its own. Either wait gives up once that turn has
        shown no activity for `turn_stall_timeout_s`. If interrupt() is called
        while this request is still waiting, it is never sent, and ask()
        yields only an error TurnDone.

        Args:
            text: The user's request, already stripped of the wake phrase.

        Yields:
            ReplyText for each assistant text block, in order, then exactly one TurnDone.

        Raises:
            RuntimeError: start() hasn't been called, or the session has ended.
            TurnStalledError: Claude showed no activity on this request for
                `turn_stall_timeout_s`. The CLI is asked to stop it, and the next
                ask() waits for that (or for it to stall again).
        """
        stall_timeout_s = self._settings.turn_stall_timeout_s
        interrupts_at_entry = self._interrupt_count
        async with self._ask_lock:
            await self._router.wait_until_idle(stall_timeout_s)
            if self._interrupt_count == interrupts_at_entry:
                await self._keeper.prepare_turn()  # voice pick and MCP servers; can be slow
            if self._interrupt_count != interrupts_at_entry:
                # "Stop" came while this request waited its turn or the session was
                # prepared. Sending it now would let auto-allowed tools run after "stop".
                logger.info("not sending a request that was stopped while it waited")
                event = TurnDone(duration_s=0.0, cost_usd=None, is_error=True)
            else:
                # The hub's transcript, never model text: the hand-off quotes it as the owner's.
                self._main_session.note_request(text)
                turn_events = await self._send(text)
                event = await next_turn_event(
                    self._router, self._keeper.session, turn_events, stall_timeout_s
                )
                while not isinstance(event, TurnDone):
                    if isinstance(event, ReplyText):
                        yield event
                    event = await next_turn_event(
                        self._router, self._keeper.session, turn_events, stall_timeout_s
                    )
        # The turn is over, so release the lock before the final yield. A caller
        # that stops right at TurnDone (without closing the iterator) can't block
        # the next ask().
        yield event

    async def interrupt(self) -> None:
        """Stop the turn Claude is working on. Its ask() then ends with an error TurnDone.

        An ask() still waiting for an earlier or injected turn is cancelled
        too: it won't send its request. Otherwise this does nothing when Claude
        is idle, so "Claude, stop" while idle is harmless.
        """
        self._interrupt_count += 1
        session = self._keeper.session
        if session is None or not self._router.is_busy:
            return
        await session.interrupt()

    async def _send(self, text: str) -> asyncio.Queue[TurnEvent]:
        """Open a turn and send the request; the turn is closed again if sending fails."""
        session = self._require_live_session()
        turn_events = self._router.begin_turn()
        try:
            await session.send(text)
        except BaseException:
            self._router.end_turn_with_error()
            raise
        return turn_events

    async def _read_events(self, session: BrainSession) -> None:
        """The session's single reader: route every event until the stream ends."""
        self._session_error = None  # a new session starts clean
        try:
            async for event in session.events():
                await self._router.route(event)
            logger.warning("The Claude session's event stream ended")
            self._session_error = RuntimeError("the Claude CLI closed its output")
        except Exception as error:
            # Recorded, not swallowed: the next ask() raises with this as its cause.
            logger.exception("Reading the Claude session failed")
            self._session_error = error
        finally:
            self._router.reset()

    def _require_live_session(self) -> BrainSession:
        """Return the session, or raise if it isn't started or its reader has stopped."""
        session = self._keeper.session
        if session is None:
            raise RuntimeError("ClaudeBrain isn't started; call start() or use `async with`.")
        if self._keeper.is_reader_done:
            raise RuntimeError(
                "The Claude session has ended; close and start the brain again."
            ) from self._session_error
        return session

    def _build_session(self, settings: BrainSettings) -> BrainSession:
        """A new, unconnected session for the keeper, wired to the gate and the hand-off."""
        return self._session_factory(settings, self._cwd, self._decide, self._main_session.hand_off)

    async def _decide(self, request: PermissionRequest) -> PermissionDecision:
        """Decide one tool call through the gate, and report it to `on_tool_call` if allowed."""
        decision = await self._gate.decide(request)
        if decision.is_allowed and self._on_tool_call is not None:
            try:
                self._on_tool_call(request.tool_name)
            except Exception:
                # Broad on purpose: a failing hook must never fail a call the gate approved.
                logger.exception("on_tool_call failed for %s", request.tool_name)
        return decision
