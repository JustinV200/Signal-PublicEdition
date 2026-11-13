"""NavigationWatch: notice a main-frame navigation during an action, and wait for it to land.

navigate, the history steps (back, forward, reload) and the pointer and key
tools run their action inside a watch. It
records the tab's main-frame navigation requests and framenavigated events.
If neither happened, settle() returns at once, so a click that only changes
the page pays nothing. (Playwright's click waits for a navigation it set off to
start; a key press doesn't, so press_key passes a short start grace, ended
early by the first navigation request.) If one did, settle() waits for it to
commit (or fail, turn into a download, or be answered 204 or 205, which never
commit), then for the new page's load event, then for a short quiet spell
with no new main-frame navigation request, so a login hand-off's redirects
(an auto-submitted form, a script redirect on load) land before the result
names the URL. Each new request restarts the wait. It is read only:
nothing is clicked, typed or evaluated in the page.
"""

import asyncio
from contextlib import suppress
from types import TracebackType

from playwright.async_api import Download, Frame, Page, Request, Response
from playwright.async_api import Error as PlaywrightError

from browser_tool.actions.context import ActionContext

# After the load event, a redirect must start within this long to be followed.
QUIET_S = 0.25
# A navigation answered with one of these never commits: the tab stays put.
NO_CONTENT_STATUSES = frozenset({204, 205})
# How long press_key gives a navigation to start: Edge sends a key's form-submit
# request about 15 ms after the press returns (measured on headless Edge).
KEY_START_GRACE_S = 0.2


def settle_max_s(ctx: ActionContext) -> float:
    """The most NavigationWatch.settle waits: the [browser] navigation timeout."""
    return float(ctx.settings.browser.navigation_timeout_s)


class NavigationWatch:
    """A context manager that follows one tab's main-frame navigations while it is open."""

    def __init__(self, page: Page) -> None:
        """Args: page: The tab the action runs in."""
        self._page = page
        self._has_navigated = False  # any main-frame request or framenavigated seen
        self._has_child_navigated = False  # a child frame's framenavigated seen
        self._is_pending = False  # a main-frame request that hasn't committed or failed
        self._changed = asyncio.Event()
        self._handlers = (
            ("request", self._on_request),
            ("requestfailed", self._on_request_failed),
            ("response", self._on_response),
            ("framenavigated", self._on_navigated),
            ("download", self._on_download),
            ("close", self._on_close),
        )

    def __enter__(self) -> "NavigationWatch":
        """Start listening to the tab's events."""
        for event, handler in self._handlers:
            self._page.on(event, handler)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Stop listening."""
        for event, handler in self._handlers:
            self._page.remove_listener(event, handler)

    @property
    def has_navigated(self) -> bool:
        """True once a main-frame navigation request or framenavigated was seen.

        Same-document steps (a hash change, history.pushState) count too, so a
        back() between them is told apart from "no previous page".
        """
        return self._has_navigated

    @property
    def has_any_navigated(self) -> bool:
        """True once the main frame or any child frame navigated (an iframe's history step)."""
        return self._has_navigated or self._has_child_navigated

    async def wait_child_only_move(self) -> None:
        """Return once a child frame navigated and the main frame stayed put for QUIET_S.

        Read only. Waits forever while the main frame navigates or nothing does;
        the caller cancels it. A history step through an iframe's history
        doesn't move the main frame, and Playwright's go_back/go_forward would
        wait out the whole navigation timeout for it.
        """
        while True:
            while not self._has_child_navigated or self._has_navigated:
                await self._next_change()
            self._changed.clear()
            try:
                await asyncio.wait_for(self._changed.wait(), QUIET_S)
            except TimeoutError:
                if not self._has_navigated:
                    return

    async def settle(self, max_s: float, start_grace_s: float = 0.0) -> None:
        """Wait, read only, until a navigation seen during the action has landed.

        Returns at once if none was seen (after start_grace_s). Never raises on a
        closed tab or a slow page: it gives up after max_s and the caller reports
        wherever the tab is.

        Args:
            max_s: The most this waits in all (the navigation timeout).
            start_grace_s: How long to wait for a navigation to start, if none has.
        """
        if start_grace_s > 0:
            with suppress(TimeoutError):
                async with asyncio.timeout(start_grace_s):
                    while not self._has_navigated and not self._page.is_closed():
                        await self._next_change()
        if not self._has_navigated:
            return
        with suppress(TimeoutError):
            async with asyncio.timeout(max_s):
                while await self._is_still_moving():
                    pass

    async def _is_still_moving(self) -> bool:
        """One round of settle(): False once the tab has loaded and stayed put for QUIET_S."""
        if self._page.is_closed():
            return False
        if self._is_pending:
            await self._next_change()
            return True
        with suppress(PlaywrightError):  # a closed tab: the next round sees it
            await self._page.wait_for_load_state("load")
        if self._is_pending:
            return True
        self._changed.clear()
        try:
            await asyncio.wait_for(self._changed.wait(), QUIET_S)
        except TimeoutError:
            return self._is_pending
        return True

    async def _next_change(self) -> None:
        """Wait for the next event any handler reports."""
        self._changed.clear()
        await self._changed.wait()

    def _is_main_navigation(self, request: Request) -> bool:
        # Only navigation requests are checked for a frame: others may have none.
        return request.is_navigation_request() and request.frame == self._page.main_frame

    def _on_request(self, request: Request) -> None:
        if self._is_main_navigation(request):
            self._has_navigated = self._is_pending = True
            self._changed.set()

    def _on_request_failed(self, request: Request) -> None:
        # A blocked hop or an aborted navigation: the tab stays where it was.
        if self._is_main_navigation(request):
            self._is_pending = False
            self._changed.set()

    def _on_response(self, response: Response) -> None:
        # A 204 or 205 answer never commits and never fails: stop waiting for it.
        if response.status in NO_CONTENT_STATUSES and self._is_main_navigation(response.request):
            self._is_pending = False
            self._changed.set()

    def _on_navigated(self, frame: Frame) -> None:
        if frame != self._page.main_frame:
            self._has_child_navigated = True
            self._changed.set()
        else:
            self._has_navigated = True
            self._is_pending = False
            self._changed.set()

    def _on_download(self, _download: Download) -> None:
        # The navigation turned into a download, which never commits.
        self._is_pending = False
        self._changed.set()

    def _on_close(self, _page: Page) -> None:
        self._changed.set()
