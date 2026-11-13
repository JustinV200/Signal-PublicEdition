"""The `Kernel` facade: the single entry point for every message bound for the user.

Producers call `submit` from any thread. The voice loop waits with
`wait_for_work`, then, once the user is free to hear, calls `next_batch` to
get what to speak, in order. Held messages (only a custom dispatcher holds;
the Sonnet one never does) stay pending and `wait_for_work` wakes again after
`hold_recheck_s`, so they are re-decided periodically. `requeue` puts back
delivered messages whose speech was cut before they played.
"""

import asyncio
import logging
import threading
import time
from types import TracebackType

from audiohub.config import KernelSettings

from .dispatch import Dispatcher
from .inbox import DEFAULT_HISTORY_LIMIT, Inbox
from .messages import Decision, OutboundMessage

logger = logging.getLogger(__name__)


class Kernel:
    """Collects user-bound messages and hands them out in the order to speak them."""

    def __init__(
        self,
        kernel_settings: KernelSettings,
        dispatcher: Dispatcher | None = None,
        history_limit: int = DEFAULT_HISTORY_LIMIT,
    ) -> None:
        """Create a kernel.

        Args:
            kernel_settings: Dispatcher model, word limit, timeouts, re-check interval.
            dispatcher: The decision maker; defaults to a Sonnet `Dispatcher`.
            history_limit: How many delivered messages to remember for de-duplication.
        """
        self._settings = kernel_settings
        self._dispatcher = dispatcher or Dispatcher(kernel_settings)
        self._inbox = Inbox(history_limit)
        # Cross-thread hand-off: submit() appends under the lock and wakes the
        # loop with call_soon_threadsafe; only the loop thread drains it.
        self._incoming_lock = threading.Lock()
        self._incoming: list[OutboundMessage] = []
        self._loop: asyncio.AbstractEventLoop | None = None
        self._work_ready = asyncio.Event()
        self._decide_lock = asyncio.Lock()
        self._last_decision_at: float | None = None

    async def start(self) -> None:
        """Bind to the running loop and connect the dispatcher ahead of time.

        A dispatcher that can't connect is logged, not raised: decisions then
        use the fallback policy until it can.
        """
        self._bind_loop()
        try:
            await self._dispatcher.start()
        except Exception:
            logger.exception("kernel dispatcher failed to start; falling back until it recovers")

    async def close(self) -> None:
        """Release the dispatcher's session.

        Undelivered messages are not spoken. Call `drain_pending` first to
        speak or record them; any still pending are listed in a warning.
        """
        with self._incoming_lock:
            undelivered = [m.id for m in self._inbox.pending()] + [m.id for m in self._incoming]
        if undelivered:
            logger.warning(
                "kernel closing with %d undelivered message(s): %s",
                len(undelivered),
                ", ".join(undelivered),
            )
        await self._dispatcher.close()

    def drain_pending(self) -> list[OutboundMessage]:
        """Remove and return every undelivered message, held ones included (loop thread only).

        Meant for shutdown, so the loop can speak or log what would otherwise
        be lost. Returns them oldest arrival first.
        """
        self._drain_incoming()
        return self._inbox.take_pending()

    async def __aenter__(self) -> "Kernel":
        await self.start()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        await self.close()

    def submit(self, message: OutboundMessage) -> None:
        """Queue a message for the user. Safe to call from any thread.

        Args:
            message: The message; build one with `create_message`.
        """
        with self._incoming_lock:
            self._incoming.append(message)
            loop = self._loop
        # Before the kernel is bound to a loop, the message just waits in
        # _incoming; _bind_loop signals it once a loop is known.
        if loop is not None:
            loop.call_soon_threadsafe(self._work_ready.set)

    @property
    def pending_count(self) -> int:
        """Messages not yet delivered or dropped, held ones included (loop thread only)."""
        with self._incoming_lock:
            return len(self._inbox) + len(self._incoming)

    async def wait_for_work(self, timeout_s: float | None = None) -> bool:
        """Wait until a message arrives or held messages are due for a re-check.

        Args:
            timeout_s: Give up after this many seconds; None waits indefinitely.

        Returns:
            True if `next_batch` has something to decide, False on timeout.
        """
        self._bind_loop()
        recheck_s = self._seconds_until_recheck()
        is_recheck_first = recheck_s is not None and (timeout_s is None or recheck_s <= timeout_s)
        wait_s = recheck_s if is_recheck_first else timeout_s
        try:
            await asyncio.wait_for(self._work_ready.wait(), wait_s)
        except TimeoutError:
            # Decide by which limit was shorter, not by re-reading the clock:
            # asyncio may fire a timer up to one clock tick early (~16 ms on
            # Windows), which would make a due re-check look not quite due.
            return is_recheck_first
        return True

    async def next_batch(self) -> list[tuple[OutboundMessage, str]]:
        """Decide on everything pending and return what to speak now, in order.

        Call it only when the user is free to hear.

        Returns:
            (message, text to speak) pairs in speaking order. The text is the
            original or the dispatcher's condensed version. Returned messages
            count as delivered; held ones stay pending.
        """
        async with self._decide_lock:
            self._bind_loop()
            self._drain_incoming()
            pending = self._inbox.pending()
            if not pending:
                return []
            decisions = await self._dispatcher.decide(pending, self._inbox.recent_delivered())
            self._last_decision_at = time.monotonic()
            return self._apply(decisions)

    def requeue(self, messages: list[OutboundMessage]) -> None:
        """Make delivered messages pending again, ahead of the rest (loop thread only).

        For messages whose speech was cut before they played: their history
        records go too, so the dispatcher can't drop them as repeats of
        themselves. They are re-decided with the next batch.

        Args:
            messages: Messages from an earlier `next_batch`, in speaking order.
        """
        self._inbox.requeue(messages)

    def _apply(self, decisions: list[Decision]) -> list[tuple[OutboundMessage, str]]:
        """Carry out decisions on the inbox and collect the deliveries in order."""
        batch: list[tuple[OutboundMessage, str]] = []
        for decision in decisions:
            message = self._inbox.get(decision.message_id)
            if message is None:
                logger.warning("decision for %s, which is not pending; ignored", decision)
                continue
            if decision.action == "deliver":
                spoken = message.text if decision.text is None else decision.text
                self._inbox.mark_delivered(message.id, spoken)
                batch.append((message, spoken))
            elif decision.action == "drop":
                self._inbox.discard(message.id)
                logger.info("dropped %s from %s: %s", message.id, message.source, decision.reason)
        return batch

    def _drain_incoming(self) -> None:
        """Move submitted messages into the inbox (loop thread only)."""
        with self._incoming_lock:
            arrived, self._incoming = self._incoming, []
            # Cleared under the lock: a submit after this point sets it again.
            self._work_ready.clear()
        for message in arrived:
            try:
                self._inbox.add(message)
            except ValueError:
                # Only a hand-built message can repeat an id; keep the first one.
                logger.error("ignoring message with duplicate id %s: %r", message.id, message.text)

    def _seconds_until_recheck(self) -> float | None:
        """Seconds until held messages should be re-decided, or None if none are held."""
        if not len(self._inbox):
            return None
        if self._last_decision_at is None:
            # Pending but never decided (the first decision was cancelled or
            # raised): due right away, or these messages would never wake anyone.
            return 0.0
        due_at = self._last_decision_at + self._settings.hold_recheck_s
        return max(0.0, due_at - time.monotonic())

    def _bind_loop(self) -> None:
        """Remember the running loop so other threads can wake it."""
        loop = asyncio.get_running_loop()
        with self._incoming_lock:
            if self._loop is None:
                self._loop = loop
            elif self._loop is not loop:
                raise RuntimeError("this Kernel is already bound to a different event loop")
            has_incoming = bool(self._incoming)
        if has_incoming:
            self._work_ready.set()
