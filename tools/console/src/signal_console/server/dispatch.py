"""Send the owner's typed messages to the claimed orchestrator, reporting each in the feed.

Each request shows at once as a "you" message, then a `delivery` event (its
own id, plus `messageId` naming the message) says whether the orchestrator's
inbox took it. Delivery runs in the background so /api/send answers 202
straight away. Every request gets exactly one delivery event, even when
something unexpected breaks, so the page never waits on it forever. Buttons
don't come here: server/action_runner.py runs them.
"""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from pathlib import Path

from signal_console.orchestrator import (
    Claim,
    ConsoleRequest,
    InboxError,
    read_claim,
    send_to_inbox,
)
from signal_console.server.events import EventHub, new_event_id, now_iso

NOT_CLAIMED_ERROR = (
    "No orchestrator session has claimed the console. Run `console claim` from that session."
)
# Shown for a bug rather than a known failure; the details go to the server log.
UNEXPECTED_ERROR = "The console hit an unexpected error sending this; see the server log."

SendToInbox = Callable[[Claim, str], Awaitable[None]]

log = logging.getLogger(__name__)


class Dispatcher:
    """Turns typed messages into inbox messages and feed events."""

    def __init__(
        self,
        events: EventHub,
        state_dir: Path,
        send: SendToInbox = send_to_inbox,
    ) -> None:
        """Wire the dispatcher.

        Args:
            events: Where the "you" message and the delivery result go.
            state_dir: Holds the claim (re-read per send, so a new claim applies at once).
            send: Writes to the inbox; tests pass a fake.
        """
        self._events = events
        self._state_dir = state_dir
        self._send = send
        # Strong references, so running deliveries aren't garbage-collected.
        self._deliveries: set[asyncio.Task[None]] = set()

    def submit(self, request: ConsoleRequest) -> str:
        """Show the request as the owner's message and start delivering it.

        Args:
            request: What to show and what to send.

        Returns:
            The message id, which the matching `delivery` event gives as `messageId`.
        """
        message_id = new_event_id()
        self._events.publish(
            "message",
            {
                "id": message_id,
                "role": "you",
                "text": request.display_text,
                "at": now_iso(),
                "kind": "chat",
            },
        )
        task = asyncio.create_task(self._deliver(message_id, request.orchestrator_text))
        self._deliveries.add(task)
        task.add_done_callback(self._finish)
        return message_id

    async def _deliver(self, message_id: str, text: str) -> None:
        try:
            error = await self._send_to_claimed(text)
        except Exception:
            log.exception("console message %s: delivery broke unexpectedly", message_id)
            error = UNEXPECTED_ERROR
        if error is not None:
            log.warning("console message %s not delivered: %s", message_id, error)
        delivery = {
            "id": new_event_id(),
            "messageId": message_id,
            "status": "sent" if error is None else "failed",
            "error": error,
        }
        # Busy is the turn hooks' to say: the page shows `sent` until the turn starts.
        self._events.publish("delivery", delivery)

    async def _send_to_claimed(self, text: str) -> str | None:
        # The error to show, or None once the inbox took the message.
        claim = read_claim(self._state_dir)
        if claim is None:
            return NOT_CLAIMED_ERROR
        try:
            await self._send(claim, text)
        except InboxError as failure:
            return str(failure)
        return None

    def _finish(self, task: asyncio.Task[None]) -> None:
        self._deliveries.discard(task)
        # Retrieve any exception (e.g. from publishing the result), so it's logged
        # here rather than as "Task exception was never retrieved" at shutdown.
        if not task.cancelled() and task.exception() is not None:
            log.error("console delivery task failed", exc_info=task.exception())
