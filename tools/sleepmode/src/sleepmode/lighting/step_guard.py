"""StepGuard: how Lighting calls off a backend step that overran its deadline.

run_with_deadline (deadline.py) stops waiting for a step but can't stop its thread.
So each backend step gets a guard. When the deadline passes, Lighting abandons it:
the connections the step registered are closed, so an openrgb-python call stuck on
its socket raises, and the step checks the guard before each device change or
command, so a late one can't turn a light off after a later wake has restored it.
"""

import logging
import threading
from collections.abc import Callable

log = logging.getLogger(__name__)


class StepGuard:
    """One backend step's leave to change the lights, until Lighting abandons it."""

    def __init__(self) -> None:
        """A guard that isn't abandoned and has nothing to close yet."""
        self._lock = threading.Lock()
        self._is_abandoned = False
        self._closers: list[Callable[[], None]] = []

    @property
    def is_abandoned(self) -> bool:
        """True once Lighting gave up on the step: it must stop before its next change."""
        return self._is_abandoned

    def close_on_abandon(self, close: Callable[[], None]) -> None:
        """Have abandon() call close, or call it now if the step is already abandoned.

        Args:
            close: Closes a connection the step uses; it must be safe to call twice,
                since the step closes it too when it finishes.
        """
        with self._lock:
            if not self._is_abandoned:
                self._closers.append(close)
                return
        close()

    def abandon(self) -> None:
        """Mark the step abandoned and close what it registered; a failed close is logged."""
        with self._lock:
            self._is_abandoned = True
            closers, self._closers = self._closers, []
        for close in closers:
            try:
                close()
            except Exception as error:  # openrgb-python raises assorted types; the step is lost
                log.warning("lighting: couldn't close an abandoned step's connection: %s", error)
