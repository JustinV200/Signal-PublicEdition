"""ResubmitGuard: hold back a form resubmission while a history step runs.

Edge re-sends a POST without asking when a tab reloads, or goes back or
forward onto, a page a form submitted to (measured on headless Edge). That
resends whatever the form sent: a message, an order. An iframe's form is
re-sent the same way when the step goes through the iframe's history. While
the guard is open, a POST navigation in any frame of the tab is aborted with
ERR_ABORTED, which leaves the frame on the page it was on (a blocked-by-client
error would show an error page instead), and the guard notes it, so the
caller can run the send rule and step again with the guard off. Every other request falls through to
the context's request guard (session.request_guard).
"""

import asyncio
import logging
from types import TracebackType

from playwright.async_api import Error as PlaywrightError
from playwright.async_api import Page, Route

logger = logging.getLogger(__name__)

ALL_URLS = "**/*"
# The abort code that cancels a navigation without committing an error page.
KEEP_PAGE_ABORT = "aborted"


class ResubmitGuard:
    """An async context manager that aborts POST navigations in any frame of the tab.

    Attributes:
        blocked: Set once a resubmission was held back (awaitable).
    """

    def __init__(self, page: Page, *, is_active: bool = True) -> None:
        """Args: page: The tab. is_active: False lets every request through."""
        self._page = page
        self._is_active = is_active
        self.blocked = asyncio.Event()

    @property
    def was_blocked(self) -> bool:
        """True once a resubmission was held back."""
        return self.blocked.is_set()

    async def __aenter__(self) -> "ResubmitGuard":
        """Start routing the tab's requests through the guard."""
        if self._is_active:
            await self._page.route(ALL_URLS, self._route)
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Stop routing."""
        if self._is_active and not self._page.is_closed():
            await self._page.unroute(ALL_URLS, self._route)

    async def _route(self, route: Route) -> None:
        request = route.request
        try:
            # Any frame: an iframe's form is re-sent by a history step too.
            if request.is_navigation_request() and request.method == "POST":
                self.blocked.set()
                await route.abort(KEEP_PAGE_ABORT)
                return
            await route.fallback()
        except PlaywrightError as error:
            # Usually the tab closed mid-request. Type only: messages can hold URLs.
            logger.debug("resubmit guard routing failed: %s", type(error).__name__)
