"""LoginLoopGuard: stop refilling a login that keeps asking again. Pure: no Playwright.

A normal sign-in is one fill_login; a wrong password or a flaky form earns one
retry. A third fill on the same site within LOOP_WINDOW_S means the login isn't
working (a wrong saved password, a lockout, a broken redirect back to the login
page). Filling again would only repeat it, and repeated wrong passwords can lock
the account, so that fill is refused until the oldest fill leaves the window.

Fills are counted, not page landings: federated and SSO logins pass through
choosers and hand-off pages that would read as a return to the login page. The
guard only ever refuses more: it never allows or adds a fill.
"""

import time
from collections.abc import Callable

# How long a fill counts toward the limit.
LOOP_WINDOW_S = 600.0
# Fills allowed per site per window: the login plus one retry.
MAX_FILLS_PER_WINDOW = 2


class LoginLoopGuard:
    """Counts recent fills per site and refuses one past MAX_FILLS_PER_WINDOW."""

    def __init__(self, clock: Callable[[], float] = time.monotonic):
        """Start with no fills.

        Args:
            clock: Monotonic seconds; tests pass a fake.
        """
        self._clock = clock
        self._fills: dict[str, list[float]] = {}

    def note_fill(self, site: str) -> None:
        """Record a fill on `site` (a hostname)."""
        self._fills.setdefault(site, []).append(self._clock())

    def is_loop(self, site: str) -> bool:
        """True when `site` already had MAX_FILLS_PER_WINDOW fills under LOOP_WINDOW_S ago."""
        now = self._clock()
        recent = [at for at in self._fills.get(site, []) if now - at < LOOP_WINDOW_S]
        self._fills[site] = recent
        return len(recent) >= MAX_FILLS_PER_WINDOW
