"""NightGuard: keeps the projector dark all night, retrying the whiteboard's night view.

The projector starts under a black window, the stop-gap while the whiteboard is down
or starting. Every NIGHT_RETRY_S a check runs on a worker thread (an HTTP call on the
keeper's thread could stall the input hooks long enough for Windows to drop them):
- covered: if the night view isn't up, ask for it (the whiteboard may have started
  since); if it's still not on a page, repair the whiteboard (start its daemon, or
  have it reopen its kiosk) so the next check finds it; once it's up, close the
  projector's black window;
- uncovered: if the night view is gone (the daemon stopped, or its kiosk closed), put
  the black window back. The show is retried only on the next check, so a wake that
  has just hidden the night view isn't undone before the keeper exits.
The windows are created and closed on the keeper's thread, in poll(). close() waits
(up to CLOSE_WAIT_S) for a check still running, so its show can't land after the
wake's hide.
"""

import logging
import threading
import time
from collections.abc import Callable
from concurrent.futures import Future
from dataclasses import dataclass

from sleepmode.keeper.blackout import BlackoutWindows

log = logging.getLogger(__name__)

NIGHT_RETRY_S = 60.0
# A check makes up to 3 whiteboard requests; 2 of whiteboard_link's 5 s timeouts covers
# a show in flight without holding the keeper's exit up for long.
# A wake's stop_keeper may end the keeper after KEEPER_EXIT_WAIT_S anyway; wake_up's
# second hide covers that case.
CLOSE_WAIT_S = 10.0

Rect = tuple[int, int, int, int]


@dataclass(frozen=True)
class NightView:
    """The keeper's link to the whiteboard (built in sleepmode.wiring).

    Attributes:
        is_showing: True if the night view is on the projector; may raise.
        show: Asks for the night view; may raise.
        repair: Starts the whiteboard daemon if it's down, else asks it to reopen its
            kiosk (whiteboard_link.repair_night_view); may raise.
    """

    is_showing: Callable[[], bool]
    show: Callable[[], None]
    repair: Callable[[], None]


def _in_daemon_thread(check: Callable[[], bool]) -> "Future[bool]":
    """Run check on a daemon thread, so a slow whiteboard never holds up the keeper's exit."""
    future: Future[bool] = Future()
    threading.Thread(target=lambda: future.set_result(check()), daemon=True).start()
    return future


class NightGuard:
    """The projector's black window, shown whenever the night view isn't."""

    def __init__(
        self,
        rect: Rect,
        view: NightView,
        cover: Callable[[list[Rect]], BlackoutWindows] = BlackoutWindows,
        run: Callable[[Callable[[], bool]], "Future[bool]"] = _in_daemon_thread,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        """Cover the projector now; the first check runs on the first poll.

        Args:
            rect: The projector's physical (x, y, width, height).
            view: The whiteboard calls.
            cover: Opens black windows; tests pass a fake.
            run: Runs a check off the keeper's thread; tests run it inline.
            clock: Monotonic seconds; tests pass a fake.

        Raises:
            OSError: The black window couldn't be created.
        """
        self._rect, self._view, self._cover_with = rect, view, cover
        self._run, self._clock = run, clock
        self._cover: BlackoutWindows | None = cover([rect])
        self._pending: Future[bool] | None = None
        self._next_check = clock()

    def poll(self) -> None:
        """Start a check when one is due, and act on one that has finished."""
        if self._pending is None:
            if self._clock() >= self._next_check:
                is_covered = self._cover is not None
                self._pending = self._run(lambda: self._check(is_covered))
            return
        if not self._pending.done():
            return
        is_up = self._pending.result()
        self._pending, self._next_check = None, self._clock() + NIGHT_RETRY_S
        if is_up and self._cover is not None:
            self._cover.close()
            self._cover = None
            log.info("the night view is up; uncovered the projector")
        elif not is_up and self._cover is None:
            log.warning("the night view is gone; covering the projector with a black window")
            self._cover = self._cover_with([self._rect])

    def close(self) -> None:
        """Close the projector's black window, then wait for a running check. Safe to call twice."""
        if self._cover is not None:
            self._cover.close()
            self._cover = None
        if self._pending is not None:
            try:
                self._pending.result(timeout=CLOSE_WAIT_S)
            except TimeoutError:
                log.warning("a night view check is still running after %g s", CLOSE_WAIT_S)
            self._pending = None

    def _check(self, is_covered: bool) -> bool:
        """Whether the night view is up, asking for it (and repairing) if the projector is covered.

        Only a covered projector is repaired, so a wake that just hid the night view
        never has the whiteboard started or its kiosk reopened behind it.
        """
        if self._is_up(is_covered):
            return True
        if is_covered:
            try:
                self._view.repair()
            except Exception as error:  # the next check tries again
                log.warning("couldn't repair the whiteboard's night view: %s", error)
        return False

    def _is_up(self, is_covered: bool) -> bool:
        """Whether the night view is up, asking for it first if the projector is covered."""
        try:
            if self._view.is_showing():
                return True
            if not is_covered:
                return False  # cover it first; the show waits for the next check
            self._view.show()
            return self._view.is_showing()
        except Exception as error:  # never let the worker thread die with no result
            log.debug("night view check: %s", error)
            return False
