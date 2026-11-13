"""Records the host of every main-frame navigation hop on one tab, redirects included.

navigate() turns the request guard's block log into prose, so visit keeps its own
structured record: after a failed navigation, the last hop's host says where the
tab was being sent (for example to accounts.google.com, or to CAS). Hosts only:
never URLs, which can carry tokens.
"""

import logging
from collections import deque
from urllib.parse import urlsplit

from playwright.async_api import Error as PlaywrightError
from playwright.async_api import Page, Request

logger = logging.getLogger(__name__)

MAX_HOPS = 50


class MainFrameHops:
    """The hosts of one page's main-frame navigation requests since the last reset()."""

    def __init__(self) -> None:
        """Start empty and attached to nothing."""
        self._hosts: deque[str] = deque(maxlen=MAX_HOPS)
        self._page: Page | None = None

    def attach(self, page: Page) -> None:
        """Start recording page's main-frame navigation requests."""
        self._page = page
        page.on("request", self._on_request)

    def reset(self) -> None:
        """Forget the hops so far (call before each navigation)."""
        self._hosts.clear()

    @property
    def last_host(self) -> str:
        """The last recorded hop's host, lower-cased, or "" if there was none."""
        return self._hosts[-1] if self._hosts else ""

    def _on_request(self, request: Request) -> None:
        try:
            is_main_frame = self._page is not None and request.frame == self._page.main_frame
            if not (request.is_navigation_request() and is_main_frame):
                return
        except PlaywrightError as error:
            # A request with no frame (a service worker's) isn't a main-frame hop.
            logger.debug("skipping a request without a frame: %s", type(error).__name__)
            return
        try:
            host = urlsplit(request.url).hostname or ""
        except ValueError:
            host = ""
        if host:
            self._hosts.append(host.lower())
