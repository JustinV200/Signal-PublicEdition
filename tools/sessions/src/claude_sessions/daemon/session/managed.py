"""ManagedSession: one headless Claude Code session the daemon drives, and its single reader task.

Life of a session: launch() starts a runner task that connects the SDK client,
sends the first prompt and then reads every message until the CLI exits. That
one reader serves all turns, including turns the CLI starts by itself when a
background agent finishes, so nothing stalls the SDK's message buffer.
send() writes further prompts; stop() disconnects. Tool calls that need
approval go to the Approver (see approval_gate.py), and turn ends, failures
and approval waits are announced through the Notifier.
"""

import asyncio
import logging
from collections.abc import Callable
from dataclasses import dataclass

from signal_hub_notify import Notifier

from claude_sessions.approvals import Approver
from claude_sessions.daemon.session.approval_gate import ApprovalGate
from claude_sessions.daemon.session.errors import SessionError
from claude_sessions.daemon.session.record import SessionRecord, SessionState
from claude_sessions.notify import session_failed_note, turn_finished_note
from claude_sessions.sdk import (
    AssistantText,
    ClientFactory,
    LaunchSpec,
    SessionClient,
    SessionEvent,
    SessionIdentified,
    SessionOptions,
    TurnEnded,
    build_options,
    make_can_use_tool,
    translate_message,
)

logger = logging.getLogger(__name__)

# Long enough for the SDK's own close: it waits for the CLI, then terminates, then kills it.
DISCONNECT_TIMEOUT_S = 25.0
CLI_EXITED = "the Claude CLI exited unexpectedly"
# States in which a live session accepts a new prompt.
_READY_STATES = frozenset({SessionState.IDLE, SessionState.ERROR})


@dataclass(frozen=True)
class SessionDeps:
    """What every managed session shares, supplied by the SessionManager.

    Attributes:
        client_factory: Builds the SDK client; tests pass a fake.
        approver: Decides tool calls the CLI would prompt for.
        notifier: Sends voice notifications to the hub.
        on_change: Called after the record changes, to persist it.
        clock: Returns the time in seconds since the epoch.
    """

    client_factory: ClientFactory
    approver: Approver
    notifier: Notifier
    on_change: Callable[[], None]
    clock: Callable[[], float]


class ManagedSession:
    """One managed session: its record, and while live, its client and runner task."""

    def __init__(self, record: SessionRecord, deps: SessionDeps) -> None:
        """Wrap a record. Nothing runs until launch().

        Args:
            record: The session's metadata; updated in place as it runs.
            deps: Shared collaborators.
        """
        self.record = record
        self._deps = deps
        self._gate = ApprovalGate(record, deps.approver, deps.notifier, self.set_state)
        self._client: SessionClient | None = None
        self._runner: asyncio.Task[None] | None = None
        self._is_stopping = False
        # The CLI reports a running cost total per process; this is the last one seen.
        self._process_cost_usd = 0.0

    @property
    def is_live(self) -> bool:
        """True while the runner task (and so the CLI process) is up."""
        return self._runner is not None and not self._runner.done()

    @property
    def pending_approval(self) -> str | None:
        """The description of the tool call waiting for approval, if any."""
        return self._gate.pending_description

    def launch(self, prompt: str, spec: LaunchSpec) -> None:
        """Start the CLI in the background and send the first prompt. Returns at once.

        Args:
            prompt: The first user message.
            spec: Where and how to launch (new session id or resume).

        Raises:
            SessionError: The session is already live.
            PermissionModeError: spec's permission mode isn't allowed.
        """
        if self.is_live:
            raise SessionError(f"Session {self.record.id} is already running; use send instead.")
        options = build_options(spec, make_can_use_tool(self._gate.decide))
        self._is_stopping = False
        self._process_cost_usd = 0.0
        self.record.error = None
        self.set_state(SessionState.WORKING)
        self._runner = asyncio.create_task(
            self._run(options, prompt), name=f"session-{self.record.id}"
        )

    async def send(self, prompt: str) -> None:
        """Send a follow-up prompt to a live, idle session.

        Args:
            prompt: The user message.

        Raises:
            SessionError: The session isn't live (resume it) or is busy.
        """
        if not self.is_live or self._client is None:
            raise SessionError(
                f"Session {self.record.id} isn't running; use resume to continue it."
            )
        if self.record.state not in _READY_STATES:
            raise SessionError(
                f"Session {self.record.id} is {self.record.state.value}; wait until it's idle."
            )
        self.set_state(SessionState.WORKING)
        try:
            await self._client.query(prompt)
        except Exception as error:
            self._fail(f"sending the prompt failed: {error}")
            raise SessionError(f"Couldn't send to session {self.record.id}: {error}") from error

    async def stop(self) -> None:
        """Stop the CLI and mark the session stopped. Safe to call when not live."""
        self._is_stopping = True
        client, runner = self._client, self._runner
        if client is not None:
            await _disconnect_quietly(client, self.record.id)
        if runner is not None and not runner.done():
            runner.cancel()
            await asyncio.wait({runner})
        self._client = None
        self.set_state(SessionState.STOPPED)

    def set_state(self, state: SessionState) -> None:
        """Change the state, stamp the time and persist.

        Args:
            state: The new state.
        """
        self.record.state = state
        self.record.updated_at = self._deps.clock()
        self._deps.on_change()

    async def _run(self, options: SessionOptions, prompt: str) -> None:
        """The runner: connect, send the first prompt, then read until the CLI exits."""
        client = self._deps.client_factory(options)
        self._client = client
        try:
            await client.connect()
            await client.query(prompt)
            async for message in client.receive_messages():
                for event in translate_message(message):
                    self._apply(event)
            if not self._is_stopping:
                self._fail(CLI_EXITED)
        except Exception as error:
            if not self._is_stopping:
                logger.exception("Session %s failed", self.record.id)
                self._fail(f"{type(error).__name__}: {error}")
        finally:
            if not self._is_stopping:
                # Make sure a failed CLI process doesn't linger.
                self._client = None
                await _disconnect_quietly(client, self.record.id)

    def _apply(self, event: SessionEvent) -> None:
        """Update the record for one event from the reader."""
        if isinstance(event, AssistantText):
            self.record.add_text(event.text)
            if self.record.state in _READY_STATES:
                # Text while idle is a turn the CLI started itself (a background agent finished).
                self.set_state(SessionState.WORKING)
        elif isinstance(event, SessionIdentified):
            self._set_claude_session_id(event.claude_session_id)
        elif isinstance(event, TurnEnded):
            self._end_turn(event)

    def _end_turn(self, event: TurnEnded) -> None:
        """Record cost and outcome of a turn, and announce it."""
        self._set_claude_session_id(event.claude_session_id)
        self._add_cost(event.session_total_cost_usd)
        if event.is_error:
            self._fail(event.error_detail or "the turn failed")
            return
        self.record.error = None
        self.set_state(SessionState.IDLE)
        final_text = event.final_text or (self.record.last_texts or [""])[-1]
        self._deps.notifier.post(turn_finished_note(self.record.repo_name, final_text))

    def _add_cost(self, process_total_usd: float | None) -> None:
        """Add the cost since the last result; a lower total means the CLI's total restarted."""
        if process_total_usd is None:
            return
        previous = self._process_cost_usd if process_total_usd >= self._process_cost_usd else 0.0
        self.record.cost_usd += process_total_usd - previous
        self._process_cost_usd = process_total_usd

    def _set_claude_session_id(self, claude_session_id: str) -> None:
        """Follow the CLI if it stores the conversation under a different id."""
        if claude_session_id and claude_session_id != self.record.claude_session_id:
            logger.info("Session %s is now Claude session %s", self.record.id, claude_session_id)
            self.record.claude_session_id = claude_session_id

    def _fail(self, detail: str) -> None:
        """Enter the error state and announce it."""
        logger.warning("Session %s error: %s", self.record.id, detail)
        self.record.error = detail
        self.set_state(SessionState.ERROR)
        self._deps.notifier.post(session_failed_note(self.record.repo_name, detail))


async def _disconnect_quietly(client: SessionClient, session_id: str) -> None:
    """Disconnect, logging (not raising) failures: the session is ending either way."""
    try:
        await asyncio.wait_for(client.disconnect(), DISCONNECT_TIMEOUT_S)
    except Exception:
        logger.exception("Disconnecting session %s failed", session_id)
