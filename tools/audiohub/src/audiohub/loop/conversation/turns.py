"""`BrainTurns`: feeds the user's requests to the brain and its replies to the kernel.

Requests go to the brain one at a time, because only one ask() may run at
once. Utterances that arrive while a turn runs are merged into one follow-up
request, joined in order, so Claude answers everything the user said instead
of working through a backlog turn by turn. The merged request is capped at
MAX_QUEUED_CHARS; when the oldest utterances must go to fit, the user is told
so out loud. A turn the brain gives up on (it stalled) is a failed turn: the
user hears BRAIN_ERROR_TEXT and the next request runs as usual. Each ReplyText
becomes a high-priority kernel message from "claude", marked as a direct reply.
"Claude, stop" empties the queue, interrupts the running turn and silences the
rest of that turn's replies.
Text Claude produces outside a turn (a background agent finishing) goes to
the kernel at normal priority.
"""

import asyncio
import contextlib
import logging
from collections.abc import AsyncGenerator, Callable
from typing import Protocol

from audiohub.brain import ReplyText, TurnDone

from ..status import StatusLine, format_duration, quote
from .outbox import (
    BACKGROUND_SOURCE,
    HUB_SOURCE,
    KernelSubmit,
    submit_direct_reply,
    submit_text,
)
from .routing import ConversationState

logger = logging.getLogger(__name__)

BRAIN_ERROR_TEXT = "Sorry, something went wrong while I was talking to Claude. Please try again."
# Longest merged follow-up request, in characters (a minute or two of speech).
# Whole utterances are dropped oldest first to fit, and the user hears
# DROPPED_SPEECH_TEXT, so nothing goes missing silently.
MAX_QUEUED_CHARS = 1500
DROPPED_SPEECH_TEXT = "Sorry, I lost some of what you said while I was busy. Please repeat it."


class VoiceBrain(Protocol):
    """What the conversation needs from `audiohub.brain.ClaudeBrain`."""

    async def start(self) -> None:
        """Connect the session."""
        ...

    async def close(self) -> None:
        """Disconnect the session."""
        ...

    def ask(self, text: str) -> AsyncGenerator[ReplyText | TurnDone, None]:
        """Stream the reply to one request, ending with TurnDone."""
        ...

    async def interrupt(self) -> None:
        """Stop the running turn early."""
        ...


class BrainTurns:
    """Runs brain turns one after another, merging requests that pile up meanwhile."""

    def __init__(
        self,
        brain: VoiceBrain,
        submit: KernelSubmit,
        state: ConversationState,
        status: StatusLine,
    ) -> None:
        """Create the worker; `run()` starts it.

        Args:
            brain: The started brain session.
            submit: Sends replies to the kernel.
            state: Told when turns start and finish.
            status: Shows thinking, queued and turn results.
        """
        self._brain = brain
        self._submit = submit
        self._state = state
        self._status = status
        self._waiting: list[str] = []
        self._has_waiting = asyncio.Event()
        self._is_turn_running = False
        self._is_turn_cancelled = False
        # Whether the user was already told that speech was dropped from the
        # requests now waiting, so the notice is spoken once per merged request.
        self._has_announced_drop = False

    def add(self, request: str) -> None:
        """Queue a request; everything queued during a turn becomes one request after it.

        If the merged request would pass MAX_QUEUED_CHARS, the oldest queued
        utterances are dropped (the newest is always kept) and the user is told,
        once per merged request.
        """
        if self._is_turn_running or self._waiting:
            self._status.show("queued", quote(request))
        self._waiting.append(request)
        is_any_dropped = False
        while len(self._waiting) > 1 and len(" ".join(self._waiting)) > MAX_QUEUED_CHARS:
            logger.warning("queued speech is too long; dropping %r", self._waiting.pop(0))
            is_any_dropped = True
        if is_any_dropped and not self._has_announced_drop:
            submit_text(self._submit, HUB_SOURCE, DROPPED_SPEECH_TEXT, "high")
            self._has_announced_drop = True
        self._has_waiting.set()

    async def run(self) -> None:
        """Handle queued requests forever (until cancelled)."""
        while True:
            await self._has_waiting.wait()
            request = " ".join(self._waiting)
            self._waiting.clear()
            self._has_waiting.clear()
            self._has_announced_drop = False
            await self._run_turn(request)

    async def cancel(self) -> None:
        """Drop queued requests, interrupt the running turn and mute its remaining replies."""
        self._waiting.clear()
        self._has_waiting.clear()
        # The dropped-speech notice belongs to the requests just discarded.
        self._has_announced_drop = False
        if self._is_turn_running:
            self._is_turn_cancelled = True
            await self._brain.interrupt()

    async def _run_turn(self, request: str) -> None:
        self._is_turn_running = True
        self._is_turn_cancelled = False
        self._state.turn_started()
        self._status.show("thinking", quote(request))
        try:
            await self._forward_replies(request)
        except Exception:
            # Broad on purpose: any SDK or CLI failure ends this turn only. The
            # user hears that it failed and the hub keeps listening.
            logger.exception("Claude turn failed for request %r", request)
            submit_text(self._submit, HUB_SOURCE, BRAIN_ERROR_TEXT, "high")
        finally:
            self._is_turn_running = False
            self._state.turn_finished()

    async def _forward_replies(self, request: str) -> None:
        # aclosing: if this task is cancelled mid-turn, the brain's generator
        # is closed here rather than whenever the garbage collector gets to it.
        async with contextlib.aclosing(self._brain.ask(request)) as events:
            async for event in events:
                if isinstance(event, TurnDone):
                    self._status.show("turn done", describe_turn(event))
                elif self._is_turn_cancelled:
                    logger.info("dropping reply from a cancelled turn: %r", event.text)
                else:
                    submit_direct_reply(self._submit, event.text)


def describe_turn(turn: TurnDone) -> str:
    """Summarise a finished turn for the status line, e.g. "brain 6.6 s, $0.0123"."""
    parts = [f"brain {format_duration(turn.duration_s)}"]
    if turn.cost_usd is not None:
        parts.append(f"${turn.cost_usd:.4f}")
    if turn.is_error:
        parts.append("ended early")
    return ", ".join(parts)


def background_forwarder(submit: KernelSubmit, status: StatusLine) -> Callable[[str], None]:
    """Build the brain's `on_background_text` callback.

    Args:
        submit: Sends the text to the kernel.
        status: Shows that background text arrived.

    Returns:
        A callback that queues the text as a normal-priority message from
        "claude-background", so the kernel decides when it is spoken.
    """

    def forward(text: str) -> None:
        if submit_text(submit, BACKGROUND_SOURCE, text, "normal") is not None:
            status.show("background", quote(text))

    return forward
