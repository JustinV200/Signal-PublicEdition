"""HttpDownloader: fetches one URL politely, honouring robots.txt and the rate limit.

Redirects are followed here, one hop at a time, and every hop gets the same checks
as the first URL: http(s) only, robots.txt, the per-host rate limit. Downloads run
in a thread so the event loop (and the lead's session) keeps going. Bodies over
the size cap are refused rather than cut, since a cut data file would be silently
wrong. FetchError messages are fixed text plus the lead's own URL, never text a
server sent (spec 7.2).
"""

import asyncio
from dataclasses import dataclass
from urllib.parse import urljoin, urlsplit

from analysis_chamber.agents.fetch.api_request import is_api_request
from analysis_chamber.agents.fetch.http import (
    FetchError,
    HttpGet,
    Response,
    http_get,
    unexpected_error,
)
from analysis_chamber.agents.fetch.ratelimit import SHARED_LIMITER, HostRateLimiter, origin_key
from analysis_chamber.agents.fetch.robots import RobotsCache

MAX_DOWNLOAD_BYTES = 200 * 1024 * 1024
MAX_REDIRECTS = 5
ALLOWED_SCHEMES = ("http", "https")
_REDIRECT_STATUSES = range(300, 400)


@dataclass(frozen=True)
class Download:
    """One fetched URL.

    Attributes:
        url: The URL after redirects.
        content_type: The checked media type, lowercased, without parameters ("" if none).
        body: The raw bytes.
    """

    url: str
    content_type: str
    body: bytes


class HttpDownloader:
    """Downloads URLs politely. One per run is fine; the rate limiter is shared."""

    def __init__(
        self,
        limiter: HostRateLimiter = SHARED_LIMITER,
        get: HttpGet = http_get,
        max_bytes: int = MAX_DOWNLOAD_BYTES,
    ) -> None:
        """Args: limiter: the per-host rate limiter; get: the blocking HTTP GET
        (tests fake it); max_bytes: the size cap."""
        self._limiter = limiter
        self._get = get
        self._max_bytes = max_bytes
        self._robots = RobotsCache(get, limiter)

    async def __call__(self, url: str) -> Download:
        """Fetch `url`, following up to MAX_REDIRECTS checked redirects.

        Raises:
            FetchError: Not http(s), refused by robots.txt (or robots.txt is
                temporarily unavailable), a network or HTTP error, too many
                redirects, larger than the size cap, or anything else (fixed
                text; the error is logged).
        """
        try:
            return await self._follow(url)
        except FetchError:
            raise
        except Exception as error:  # CancelledError is a BaseException, so it propagates
            raise unexpected_error(error) from error

    async def _follow(self, url: str) -> Download:
        """__call__ without the catch-all boundary."""
        current = url
        for _ in range(MAX_REDIRECTS + 1):
            response = await self._get_checked(current)
            if response.status not in _REDIRECT_STATUSES:
                return self._finish(current, response)
            if not response.location:
                raise FetchError(f"HTTP {response.status} without a Location")
            try:
                current = urljoin(current, response.location)
            except ValueError as error:  # e.g. "http://[bad/x"
                raise FetchError("not a valid URL") from error
        raise FetchError("too many redirects")

    async def _get_checked(self, url: str) -> Response:
        """One hop: scheme and robots.txt checks (skipped for API calls), rate limit, GET."""
        try:
            parts = urlsplit(url)
            origin = origin_key(url)
        except ValueError as error:  # e.g. an unbalanced "[" in the host, or a bad port
            raise FetchError("not a valid URL") from error
        if parts.scheme not in ALLOWED_SCHEMES or not parts.hostname:
            raise FetchError("not an http(s) URL (or a redirect to one that isn't)")
        # Data-API calls skip robots.txt (api_request.py); ordinary pages honour it.
        if not is_api_request(url) and not await self._robots.allows(url):
            raise FetchError("robots.txt disallows this URL")
        await self._limiter.wait(origin)
        try:
            return await asyncio.to_thread(self._get, url, self._max_bytes + 1)
        except OSError as error:  # URLError is an OSError; its text is server-side
            raise FetchError(f"network error ({type(error).__name__})") from error

    def _finish(self, url: str, response: Response) -> Download:
        """The Download for a final, non-redirect response."""
        if not 200 <= response.status < 300:
            raise FetchError(f"HTTP {response.status}")
        if len(response.body) > self._max_bytes:
            raise FetchError(f"larger than {self._max_bytes} bytes")
        return Download(url, response.content_type, response.body)
