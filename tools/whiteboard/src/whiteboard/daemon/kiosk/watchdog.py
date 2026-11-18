"""KioskWatchdog: opens the board kiosk, and opens it again whenever it's gone.

Edge can close on its own (an update, a crash, someone closing the window), and
nothing else reopens it: the projector then shows the desktop, or at night sleep
mode's black stop-gap window. So every CHECK_INTERVAL_S, day and night, the
watchdog checks for a connected board page (the kiosk is the page; a closed
Edge or an error page has none) and relaunches the kiosk when there's none.
Relaunching closes the old Edge first, so after the start-up open a missing page
is checked again CONFIRM_S later and only relaunched if it's still missing: a
page reloading or reconnecting (board.js, within a second) is left alone.
A relaunch that doesn't bring a page back doubles the wait before the next one,
up to 16 minutes, so a broken Edge is never spawned in a tight loop; a
connected page resets it. POST /api/kiosk/open (routes.py) runs the same check
at once, under the same backoff. stop() (on shutdown) waits out a relaunch in
flight and turns every later check, and the route, into a no-op.
"""

import asyncio
import contextlib
import logging
import threading
import time
from collections.abc import Callable
from typing import Protocol

from whiteboard.display.screen import EdgeNotFoundError

logger = logging.getLogger(__name__)

CHECK_INTERVAL_S = 30.0
# How long a missing page gets to come back before it's relaunched (after start-up).
CONFIRM_S = 5.0
# 30 s, 60 s, 2 min, 4 min, 8 min, then 16 min between relaunches that don't help.
MAX_BACKOFF_DOUBLINGS = 5


class Openable(Protocol):
    """What the watchdog relaunches: runner.Kiosk, or a fake in tests."""

    def open(self) -> None:
        """Open (or reopen) the kiosk; raises EdgeNotFoundError or OSError."""
        ...


class KioskWatchdog:
    """Relaunches the kiosk when no board page is connected, with backoff."""

    def __init__(
        self,
        kiosk: Openable,
        page_count: Callable[[], int],
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        """Set up the watchdog; nothing opens until check() or start().

        Args:
            kiosk: The kiosk to (re)open.
            page_count: How many board pages are connected now (BroadcastHub.page_count).
            clock: Monotonic seconds; tests pass a fake.
            sleep: Blocking sleep for the CONFIRM_S re-check; tests pass a fake.
        """
        self._kiosk, self._page_count, self._clock, self._sleep = kiosk, page_count, clock, sleep
        self._has_opened = False  # the start-up open skips the CONFIRM_S re-check
        self.is_stopped = False
        self._failures = 0  # relaunches in a row that no page has followed yet
        self._retry_at = 0.0
        # The loop and POST /api/kiosk/open check from different threads.
        self._lock = threading.Lock()

    def check(self) -> bool:
        """Relaunch the kiosk if no page is connected and it isn't backing off.

        Blocking (Edge and PowerShell): call it in a thread from async code.

        Returns:
            True if a relaunch was tried (it may have failed; that's logged).
        """
        with self._lock:
            if self.is_stopped or self._has_page():
                return False
            now = self._clock()
            if now < self._retry_at:
                return False
            if self._has_opened:
                # Maybe just a reload or a dropped socket: give it time to reconnect.
                self._sleep(CONFIRM_S)
                if self._has_page():
                    return False
            self._has_opened = True
            self._relaunch()
            doublings = min(self._failures, MAX_BACKOFF_DOUBLINGS)
            self._retry_at = now + CHECK_INTERVAL_S * 2**doublings
            self._failures += 1
            return True

    def stop(self) -> None:
        """Stop for good: waits for a relaunch in flight, then every check is a no-op."""
        with self._lock:
            self.is_stopped = True

    def start(self, stack: contextlib.AsyncExitStack) -> None:
        """Open the kiosk now and keep checking it, until the exit stack unwinds."""
        task = asyncio.create_task(self._run(), name="kiosk-watchdog")

        async def stop() -> None:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
            # Cancelling doesn't stop a check already in its thread; this waits it out.
            await asyncio.to_thread(self.stop)

        stack.push_async_callback(stop)

    async def _run(self) -> None:
        """Check at once, then every CHECK_INTERVAL_S."""
        while True:
            await asyncio.to_thread(self.check)
            await asyncio.sleep(CHECK_INTERVAL_S)

    def _has_page(self) -> bool:
        """True if a board page is connected; also resets the backoff."""
        if self._page_count() == 0:
            return False
        # Up again: the next time it's gone, it's reopened without backing off.
        self._failures, self._retry_at = 0, 0.0
        return True

    def _relaunch(self) -> None:
        """Open the kiosk, logging the attempt and any failure (never raises)."""
        logger.info("no board page connected; opening the kiosk (try %d)", self._failures + 1)
        try:
            self._kiosk.open()
        except (EdgeNotFoundError, OSError) as error:
            logger.error("couldn't open the kiosk: %s", error)
