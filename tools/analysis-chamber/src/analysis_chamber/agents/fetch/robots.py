"""RobotsCache: fetches and caches each host's robots.txt, following RFC 9309.

We fetch robots.txt ourselves (not RobotFileParser.read) so it goes out with our
User-Agent, a timeout and a size cap, and so the status rules are RFC 9309's:
2xx is parsed, 4xx (401/403 included) means allow-all, and 5xx or an unreachable
host is a temporary refusal that isn't cached, so a later call tries again.
"""

import asyncio
import urllib.robotparser
from urllib.parse import urljoin, urlsplit

from analysis_chamber.agents.fetch.http import USER_AGENT, FetchError, HttpGet, unexpected_error
from analysis_chamber.agents.fetch.ratelimit import HostRateLimiter, origin_key

ROBOTS_MAX_BYTES = 512 * 1024  # RFC 9309 asks crawlers to parse at least 500 KiB
ROBOTS_TIMEOUT_S = 15.0
# RFC 9309: follow at least five redirects; past that, robots.txt is "unavailable".
MAX_ROBOTS_REDIRECTS = 5
_REDIRECT_STATUSES = range(300, 400)


class RobotsCache:
    """Per-origin robots.txt answers for one downloader (keyed by origin_key)."""

    def __init__(self, get: HttpGet, limiter: HostRateLimiter) -> None:
        """Args: get: the blocking HTTP GET; limiter: the per-host rate limiter."""
        self._get = get
        self._limiter = limiter
        self._parsers: dict[str, urllib.robotparser.RobotFileParser] = {}

    async def allows(self, url: str) -> bool:
        """True if robots.txt lets our User-Agent fetch `url`.

        Raises:
            FetchError: robots.txt answered 5xx or the host was unreachable
                (a temporary refusal; not cached), the URL is invalid, or
                anything else went wrong (fixed text; the error is logged).
        """
        try:
            return await self._allows(url)
        except FetchError:
            raise
        except Exception as error:  # CancelledError is a BaseException, so it propagates
            raise unexpected_error(error) from error

    async def _allows(self, url: str) -> bool:
        """allows() without the catch-all boundary."""
        origin = origin_key(url)
        if origin not in self._parsers:
            self._parsers[origin] = await self._load(urljoin(url, "/robots.txt"))
        try:
            # can_fetch unquotes the URL and re-parses it, e.g. "u%5B@" becomes "u[@".
            return self._parsers[origin].can_fetch(USER_AGENT, url)
        except ValueError as error:
            raise FetchError("not a valid URL") from error

    async def _load(self, robots_url: str) -> urllib.robotparser.RobotFileParser:
        """Fetch and parse robots.txt, following a few redirects."""
        parser = urllib.robotparser.RobotFileParser(robots_url)
        url = robots_url
        for _ in range(MAX_ROBOTS_REDIRECTS + 1):
            await self._limiter.wait(origin_key(url))
            try:
                response = await asyncio.to_thread(
                    self._get, url, ROBOTS_MAX_BYTES, ROBOTS_TIMEOUT_S
                )
            except OSError as error:
                raise FetchError("robots.txt unreachable; try again later") from error
            if response.status in _REDIRECT_STATUSES and response.location:
                target = _redirect_target(url, response.location)
                if target is None:
                    break  # RFC 9309: an unfollowable redirect makes robots.txt unavailable
                url = target
                continue
            if response.status >= 500:
                raise FetchError(f"robots.txt answered HTTP {response.status}; try again later")
            if 200 <= response.status < 300:
                try:
                    parser.parse(response.body.decode("utf-8", errors="replace").splitlines())
                except ValueError:  # e.g. "Crawl-delay: ²": isdigit passes, int fails
                    break  # unparseable: unavailable, like the cases above
                return parser
            break  # 4xx and anything else: unavailable
        parser.allow_all = True
        return parser


def _redirect_target(url: str, location: str) -> str | None:
    """The redirect's absolute URL, or None if it isn't http(s) or doesn't parse."""
    try:
        target = urljoin(url, location)
        origin_key(target)
    except ValueError:  # e.g. "http://[bad/x", or a port out of range
        return None
    return target if urlsplit(target).scheme in ("http", "https") else None
