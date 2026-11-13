"""TurnRouter: sends each session event to the ask() waiting for it, or to the background handler.

ClaudeBrain runs one reader task for the whole session and passes every event
through route(). Reading continuously (not only during ask()) matters for two
reasons. First, the CLI injects turns of its own, for example when a background
agent finishes or another session sends a message, and those must not be
mistaken for the reply to the next request. Second, the SDK's message buffer
must not fill up between turns.

Routing rules:
- Events go to the open ask() turn.
- Any event with no turn open, except a subagent's TurnActivity, starts an
  "injected turn". Its text, and any more text until a result arrives, goes to
  on_background_text. ask() waits for an injected turn to end before sending,
  because the CLI would fold the request into that turn and never answer it
  with a result of its own.
- Any result (TurnDone or InjectedTurnDone) ends both the injected turn and the
  open ask() turn. If a request was folded into an injected turn after all
  (a race), that turn's result is the only one coming.
- A turn the watchdog gave up on (abandon_turn) is treated like an injected
  one from then on: its late text goes to the background, and the next ask()
  waits for its result.
"""

import asyncio
import contextlib
import inspect
import logging
import time
from collections.abc import Awaitable, Callable

from audiohub.brain.events import (
    InjectedTurnDone,
    ReplyText,
    SessionEvent,
    TurnActivity,
    TurnDone,
)

logger = logging.getLogger(__name__)

BackgroundTextHandler = Callable[[str], Awaitable[None] | None]
"""Receives text Claude wrote outside any ask(), e.g. after a background agent finished."""

TurnEvent = ReplyText | TurnActivity | TurnDone
"""What arrives on an ask() turn's queue. TurnDone is always the last."""


class TurnRouter:
    """Tracks the open ask() turn and any injected turn, and routes session events around them."""

    def __init__(self, on_background_text: BackgroundTextHandler | None) -> None:
        """Create a router with no turn open.

        Args:
            on_background_text: Gets injected-turn text. It may be sync or async, and
                should return quickly because the session's reader waits for it.
                None means such text is logged and dropped.
        """
        self._on_background_text = on_background_text
        self._turn_events: asyncio.Queue[TurnEvent] | None = None
        self._turn_started_at = 0.0
        self._is_injected_turn_running = False
        # When the running turn (ours or injected) last showed signs of life.
        self._last_activity_at = time.monotonic()
        self._is_idle = asyncio.Event()
        self._is_idle.set()

    @property
    def is_turn_open(self) -> bool:
        """True from begin_turn() until that turn's result has been routed."""
        return self._turn_events is not None

    @property
    def is_busy(self) -> bool:
        """True while Claude is working on an ask() turn or a turn it injected."""
        return self.is_turn_open or self._is_injected_turn_running

    async def wait_until_idle(self, stall_timeout_s: float) -> None:
        """Wait until no ask() turn is open and no injected turn is running.

        Args:
            stall_timeout_s: A turn that shows no activity for this long is
                assumed lost (its result never came) and forgotten, so one
                missing result can't block every later ask().
        """
        while not self._is_idle.is_set():
            remaining_s = self._last_activity_at + stall_timeout_s - time.monotonic()
            if remaining_s <= 0:
                logger.warning(
                    "Claude's turn showed no activity for %.0f s; no longer waiting for it",
                    stall_timeout_s,
                )
                self.reset()
                return
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(self._is_idle.wait(), remaining_s)

    def begin_turn(self) -> asyncio.Queue[TurnEvent]:
        """Open a turn for one ask(). Call only after wait_until_idle().

        Returns:
            The queue this turn's ReplyText, TurnActivity and TurnDone events will arrive on.

        Raises:
            RuntimeError: A turn is already open.
        """
        if self._turn_events is not None:
            raise RuntimeError("A turn is already open; wait_until_idle() first.")
        self._turn_events = asyncio.Queue()
        self._turn_started_at = self._last_activity_at = time.monotonic()
        self._update_idle()
        return self._turn_events

    def abandon_turn(self) -> None:
        """Stop waiting for the open ask() turn, but treat it as still running in the background.

        For a turn the watchdog gave up on: its late text goes to
        on_background_text, interrupt() still reaches it (it counts as busy),
        and the next ask() waits for its result, or for it to stall too.
        """
        if self._turn_events is None:
            return
        self._turn_events = None
        self._is_injected_turn_running = True
        self._last_activity_at = time.monotonic()
        self._update_idle()

    def reset(self) -> None:
        """Forget all turn state, e.g. when the session ends, so a restarted session starts clean.

        Fails the open ask() turn, and forgets an injected turn that never got its
        result. Otherwise the next session's first reply would go to the background.
        """
        self._is_injected_turn_running = False
        self.end_turn_with_error()
        self._update_idle()

    def end_turn_with_error(self) -> None:
        """End the open turn, if any, with an error TurnDone (failed send, stall, session end)."""
        if self._turn_events is None:
            return
        self._finish_turn(TurnDone(duration_s=self._turn_elapsed_s(), cost_usd=None, is_error=True))

    async def route(self, event: SessionEvent) -> None:
        """Deliver one session event to wherever it belongs.

        Args:
            event: The next event from the session's stream.
        """
        if isinstance(event, TurnDone | InjectedTurnDone):
            self._route_result(event)
            return
        if isinstance(event, TurnActivity) and event.is_subagent and self._turn_events is None:
            # A subagent at work never starts an injected turn (background agents
            # stream between turns), but it does keep a running one alive, e.g.
            # a long foreground subagent inside a turn Claude started itself.
            if self._is_injected_turn_running:
                self._last_activity_at = time.monotonic()
            return
        self._last_activity_at = time.monotonic()
        if self._turn_events is not None and not self._is_injected_turn_running:
            self._turn_events.put_nowait(event)
            return
        if not self._is_injected_turn_running and isinstance(event, TurnActivity):
            # Nothing is spoken until its text arrives, so say why requests now wait.
            logger.info(
                "Claude started a turn on its own (first event: %s); requests wait for it",
                event.source or "activity",
            )
        self._is_injected_turn_running = True
        self._update_idle()
        if isinstance(event, ReplyText):
            await self._deliver_background_text(event.text)

    def _route_result(self, event: TurnDone | InjectedTurnDone) -> None:
        """End the injected turn and the open ask() turn, whichever this result belongs to."""
        # Any result ends an injected run, so one mislabelled result can't leave
        # later replies stuck in the background.
        self._is_injected_turn_running = False
        if self._turn_events is not None:
            if isinstance(event, InjectedTurnDone):
                logger.warning("a turn Claude started itself ended; ending the open request too")
                event = TurnDone(duration_s=self._turn_elapsed_s(), cost_usd=None, is_error=False)
            self._finish_turn(event)
        elif isinstance(event, InjectedTurnDone):
            logger.info("Claude finished a turn it started on its own")
        else:
            logger.info("Ignoring a turn result with no request waiting for it")
        self._update_idle()

    def _finish_turn(self, event: TurnDone) -> None:
        """Hand the final event to the turn's queue and close the turn."""
        queue = self._turn_events
        self._turn_events = None
        self._update_idle()
        if queue is not None:
            queue.put_nowait(event)

    def _turn_elapsed_s(self) -> float:
        return time.monotonic() - self._turn_started_at

    def _update_idle(self) -> None:
        """Keep the idle event in step: set only with no ask() turn and no injected turn."""
        if self.is_busy:
            self._is_idle.clear()
        else:
            self._is_idle.set()

    async def _deliver_background_text(self, text: str) -> None:
        """Pass injected-turn text to the handler, which may be sync or async."""
        if self._on_background_text is None:
            logger.info("No background-text handler; dropping: %s", text)
            return
        try:
            result = self._on_background_text(text)
            if inspect.isawaitable(result):
                await result
        except Exception:
            # One bad delivery must not stop the session's reader.
            logger.exception("on_background_text failed; that text was not delivered")
