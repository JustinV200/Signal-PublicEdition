"""Close the browser after a quiet spell: no tool call for the backend's idle_close_s.

Only the docker backend sets it ([browser] idle_close_min), so a container job
that the model has stopped using doesn't keep running. The ToolRunner cancels
the timer when a call starts and arms it when the call ends, so it never fires
mid-call. The close waits for the runner's lock, and a call that slipped in
between the timer firing and the close running cancels it (the generation
check), so a just-used browser isn't closed under the model.
"""

import asyncio
import logging
from collections.abc import Awaitable, Callable

logger = logging.getLogger(__name__)


class IdleClose:
    """A restartable timer that closes the session once nothing has used it for idle_s."""

    def __init__(
        self,
        idle_s: float | None,
        lock: asyncio.Lock,
        close: Callable[[], Awaitable[None]],
    ):
        """Create a disarmed timer.

        Args:
            idle_s: Quiet seconds before closing, or None to never close.
            lock: The ToolRunner's one-at-a-time lock; the close holds it.
            close: Closes the session (BrowserSession.close).
        """
        self._idle_s = idle_s
        self._lock = lock
        self._close = close
        self._generation = 0
        self._timer: asyncio.TimerHandle | None = None
        # Strong references, so a pending close task isn't garbage-collected.
        self._tasks: set[asyncio.Task[None]] = set()

    def cancel(self) -> None:
        """Stop the timer, and any close that has fired but not yet run."""
        self._generation += 1
        if self._timer is not None:
            self._timer.cancel()
            self._timer = None

    def arm(self) -> None:
        """Start the quiet-spell timer again (call from the event loop)."""
        self.cancel()
        if self._idle_s is None:
            return
        generation = self._generation
        loop = asyncio.get_running_loop()
        self._timer = loop.call_later(self._idle_s, self._fire, generation)

    def _fire(self, generation: int) -> None:
        task = asyncio.ensure_future(self._close_if_still_idle(generation))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def _close_if_still_idle(self, generation: int) -> None:
        async with self._lock:
            if generation != self._generation:
                return
            logger.info("no tool call for %.0f s; closing the browser", self._idle_s)
            try:
                await self._close()
            except Exception as error:  # noqa: BLE001 - a background task has no caller to tell
                logger.error("idle close failed: %s", type(error).__name__)
