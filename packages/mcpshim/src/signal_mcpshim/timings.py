"""Tunable delays for the shim, and the crash-loop backoff that uses them.

Defaults suit Claude Code; tests pass tiny values so a crash loop runs in milliseconds.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ShimTimings:
    """Every delay the shim uses, in seconds.

    Attributes:
        first_respawn_delay: wait before the first respawn after a crash.
        max_respawn_delay: the backoff never waits longer than this.
        stable_uptime: a child that stayed up this long resets the backoff.
        ready_timeout: how long a message waits for a restarting child (and how long the
            replayed initialize may take) before the shim gives up on it.
        shutdown_grace: how long a child gets to exit after its stdin closes before it's killed.
    """

    first_respawn_delay: float = 0.5
    max_respawn_delay: float = 30.0
    stable_uptime: float = 60.0
    ready_timeout: float = 15.0
    shutdown_grace: float = 3.0


class Backoff:
    """Exponential respawn delay: doubles per crash, capped, reset by a stable run."""

    def __init__(self, timings: ShimTimings) -> None:
        """Start at the first delay from `timings`."""
        self._timings = timings
        self._next_delay = timings.first_respawn_delay

    def next_delay(self, uptime: float) -> float:
        """Return how long to wait before respawning a child that ran for `uptime` seconds."""
        if uptime >= self._timings.stable_uptime:
            self._next_delay = self._timings.first_respawn_delay
        delay = self._next_delay
        self._next_delay = min(delay * 2, self._timings.max_respawn_delay)
        return delay
