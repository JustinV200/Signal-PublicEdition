"""Run the owner's console buttons in the background, reporting each in the feed.

Each click shows at once as a "you" action message, then a `delivery` event
(`running`), then exactly one more: `done` with `result` (what happened, in
words) or `failed` with `error`. Actions that share a lock (all voice ones, all
board ones) never overlap: a click while one runs is refused with ActionBusy,
so a double click can't start two hubs or two calibrations. A voice start frees
its lock once the hub is spawned, so Stop works while the hub loads.
"""

import asyncio
import logging
from pathlib import Path
from typing import Protocol

from signal_console.actions import BOARD_LOCK, ActionPlan, ActionTools, StepFailed, run_step
from signal_console.server.events import EventHub, new_event_id, now_iso

# Shown for a bug rather than a known failure; the details go to the server log.
UNEXPECTED_ERROR = "The console hit an unexpected error running this; see the server log."
_BUSY_WORDS = {
    "voice": "Voice is still starting or stopping; wait for that to finish.",
    "board": "The whiteboard is still busy with the last button; wait for that to finish.",
}

log = logging.getLogger(__name__)


class ActionBusy(RuntimeError):
    """An action with the same lock is still running."""


class Refreshable(Protocol):
    """The status watcher, re-read after an action so the page sees the change at once."""

    async def refresh(self, *, read_boards: bool) -> None:
        """Re-read the status now (boards only when due) and publish `state` if it changed."""
        ...

    async def saves(self) -> dict[str, str | None]:
        """Re-read the whiteboard now, whenever it was last read, and publish any change."""
        ...


class ActionRunner:
    """Runs action plans off the request path, one at a time per lock."""

    def __init__(
        self,
        events: EventHub,
        state_dir: Path,
        status: Refreshable,
        tools: ActionTools | None = None,
    ) -> None:
        """Wire the runner.

        Args:
            events: Where the action message and its results go.
            state_dir: The console's .state folder (the hub's record and log).
            status: Refreshed after each action (the board read forced after a board one).
            tools: What the steps call; tests pass fakes.
        """
        self._events = events
        self._state_dir = state_dir
        self._status = status
        self._tools = tools or ActionTools()
        self._busy_locks: set[str] = set()
        # Strong references, so running actions aren't garbage-collected.
        self._running: set[asyncio.Task[None]] = set()

    def submit(self, plan: ActionPlan) -> str:
        """Show the click and start running it.

        Returns:
            The action message's id, which its `delivery` events name as `messageId`.

        Raises:
            ActionBusy: An action with the same lock is still running.
        """
        if plan.lock in self._busy_locks:
            raise ActionBusy(_BUSY_WORDS.get(plan.lock, "That is still running."))
        self._busy_locks.add(plan.lock)
        message_id = new_event_id()
        message = {
            "id": message_id,
            "role": "you",
            "text": plan.display_text,
            "at": now_iso(),
            "kind": "action",
        }
        self._events.publish("message", message)
        self._publish_delivery(message_id, "running")
        task = asyncio.create_task(self._run(message_id, plan))
        self._running.add(task)
        task.add_done_callback(self._finish)
        return message_id

    async def _run(self, message_id: str, plan: ActionPlan) -> None:
        released = False

        def unlock() -> None:
            # One-shot: once freed early, another action may hold the lock, so never free it again.
            nonlocal released
            if not released:
                released = True
                self._busy_locks.discard(plan.lock)

        try:
            result = await run_step(plan.step, self._state_dir, self._tools, unlock)
            self._publish_delivery(message_id, "done", result=result)
        except StepFailed as failure:
            self._publish_delivery(message_id, "failed", error=str(failure))
        except Exception:
            log.exception("console action %r broke unexpectedly", plan.display_text)
            self._publish_delivery(message_id, "failed", error=UNEXPECTED_ERROR)
        finally:
            unlock()
        await self._status.refresh(read_boards=False)
        if plan.lock == BOARD_LOCK:
            # refresh() skips a board read made in the last BOARD_POLL_S, so force one.
            await self._status.saves()

    def _publish_delivery(
        self, message_id: str, status: str, *, result: str | None = None, error: str | None = None
    ) -> None:
        delivery = {"id": new_event_id(), "messageId": message_id, "status": status}
        if result is not None:
            delivery["result"] = result
        if error is not None:
            delivery["error"] = error
        self._events.publish("delivery", delivery)

    def _finish(self, task: asyncio.Task[None]) -> None:
        self._running.discard(task)
        # Retrieve any exception (e.g. from the refresh), so it's logged here
        # rather than as "Task exception was never retrieved" at shutdown.
        if not task.cancelled() and task.exception() is not None:
            log.error("console action task failed", exc_info=task.exception())
