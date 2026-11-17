"""HostRateLimiter: at most one request per second to any one origin, across every run.

One limiter is shared by the whole daemon process (SHARED_LIMITER), since runs
fetching from the same host in parallel must still be polite to it together.
`origin_key` is the key it and the robots.txt cache both use.
"""

import asyncio
import time
from collections.abc import Callable
from urllib.parse import urlsplit

MIN_INTERVAL_S = 1.0
DEFAULT_PORTS = {"http": 80, "https": 443}


def origin_key(url: str) -> str:
    """`scheme://hostname:port` for `url`, so `EX.org` and `ex.org:443` are one origin.

    The hostname is lowercased (urlsplit does that) and a missing port becomes
    the scheme's default. http and https on one host stay separate, since
    RFC 9309 gives each its own robots.txt.

    Raises:
        ValueError: The URL or its port doesn't parse.
    """
    parts = urlsplit(url)
    port = parts.port or DEFAULT_PORTS.get(parts.scheme, "")
    return f"{parts.scheme}://{parts.hostname or ''}:{port}"


class HostRateLimiter:
    """Spaces requests to each host at least `min_interval_s` apart."""

    def __init__(
        self, min_interval_s: float = MIN_INTERVAL_S, clock: Callable[[], float] = time.monotonic
    ) -> None:
        """Args: min_interval_s: the gap per host; clock: a monotonic clock (tests fake it)."""
        self._min_interval_s = min_interval_s
        self._clock = clock
        self._next_slot: dict[str, float] = {}
        self._lock = asyncio.Lock()

    async def wait(self, host: str) -> None:
        """Sleep until a request to `host` (an origin_key) is allowed, and book that slot."""
        async with self._lock:
            now = self._clock()
            slot = max(now, self._next_slot.get(host, now))
            self._next_slot[host] = slot + self._min_interval_s
        await asyncio.sleep(slot - now)


SHARED_LIMITER = HostRateLimiter()
