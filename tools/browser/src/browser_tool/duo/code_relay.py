"""CodeRelay: after a Duo prompt starts, looks for its verification code and hands it on once.

DuoWatch starts it for each new prompt. It runs as a background task per tab,
because event handlers must not block the tool: every [duo] code_poll_interval_s
it reads the tab's Duo frames (code_reader), and it stops on the first code,
when the tab stops qualifying (below), leaves Duo or closes, or after
code_relay_timeout_s. Then it calls `on_code` once, so a prompt never gets more
than one code. Duo's "send another push" inside the same prompt shows a new
code, which is therefore not relayed.

Anti-MFA-fatigue: someone who has the owner's password could start a real Duo
login and show the real Duo prompt from their own page; reading that code out
would prime the owner to approve them. So a code is relayed only when all of
these hold, checked when the relay starts, on every poll, and again right
before the code is handed on:
- the tab's top-level page is on Duo (a readable Duo host): the Universal
  Prompt, which Duo doesn't allow in an iframe. A Duo frame embedded by any
  page is never read;
- the prompt has a site (prompt_state: the tab's last non-Duo top-level host,
  vetted by DuoWatch against the navigation's redirect chain and Referer), and
  it matches [duo] code_relay_sites (empty by default: nothing is relayed until
  the owner opts a site in);
- the top-level Duo document was not reached through back/forward history, and
  is the same document from before the code was read until after that check.
"""

import asyncio
import logging
from collections.abc import Callable

from playwright.async_api import Error as PlaywrightError
from playwright.async_api import Page

from browser_tool.config import DuoSettings
from browser_tool.duo.code_reader import read_verification_code
from browser_tool.duo.failure_log import log_failure
from browser_tool.duo.hosts import is_duo_host
from browser_tool.duo.messages import shown_site
from browser_tool.duo.prompt_state import TabDuoState
from browser_tool.policy import HostPolicy, host_of

logger = logging.getLogger(__name__)

# on_code(page, site, code): the prompt in `page`, on allowlisted `site`, shows `code`.
OnCode = Callable[[Page, str, str], None]
# The Navigation Timing type of a document loaded by an ordinary navigation. Others
# are "reload", "back_forward" and "prerender"; only this one is trusted.
FRESH_NAVIGATION_TYPE = "navigate"
_NAVIGATION_TYPE_JS = "() => performance.getEntriesByType('navigation')[0]?.type ?? ''"
# Unique per document, and unchanged by same-document URL changes (pushState, #hash).
_DOCUMENT_ID_JS = "() => performance.timeOrigin"


class CodeRelay:
    """One code-reading task per tab in a top-level Duo prompt, on allowlisted sites only."""

    def __init__(self, settings: DuoSettings, on_code: OnCode):
        """Parse the site allowlist; nothing runs until start().

        Args:
            settings: The [duo] settings (code_relay_sites and the two timings).
            on_code: Called with the tab, the allowlisted site and the code, at most
                once per prompt, from the event loop.

        Raises:
            ValueError: If a code_relay_sites pattern is malformed.
        """
        try:
            # The [policy] matcher: "example.com" or "*.example.com", IDNA-normalized.
            self._sites = HostPolicy.from_strings(settings.code_relay_sites, ())
        except ValueError as error:
            raise ValueError(f"[duo] code_relay_sites: {error}") from error
        self._timeout_s = settings.code_relay_timeout_s
        self._interval_s = settings.code_poll_interval_s
        self._on_code = on_code
        self._tasks: dict[Page, asyncio.Task[None]] = {}

    def start(self, page: Page, state: TabDuoState) -> None:
        """Look for the code of the prompt the tab just entered. Call from the event loop.

        Args:
            page: The tab.
            state: Its Duo state; the relay stops once state.is_in_duo turns False.
        """
        self.stop(page)
        if self._relay_site(page, state) is None:
            return
        task = asyncio.create_task(self._relay(page, state), name="duo-code-relay")
        self._tasks[page] = task
        task.add_done_callback(lambda done: self._forget(page, done))

    def stop(self, page: Page) -> None:
        """Stop looking for a code in `page` (it left Duo or closed, or a new prompt began)."""
        task = self._tasks.pop(page, None)
        if task is not None:
            task.cancel()

    async def drain(self) -> None:
        """Wait until every running relay has finished (tests)."""
        while pending := [task for task in self._tasks.values() if not task.done()]:
            await asyncio.gather(*pending, return_exceptions=True)

    def _relay_site(self, page: Page, state: TabDuoState) -> str | None:
        """The allowlisted site the prompt may be relayed under now; None (logged) to stop."""
        site, why_not = self._judge(page, state)
        if site is None:
            logger.info("Duo code not relayed: %s", why_not)
        return site

    def _judge(self, page: Page, state: TabDuoState) -> tuple[str | None, str]:
        """(site, "") when the prompt may be relayed now, else (None, the reason)."""
        if page.is_closed():
            return None, "the tab closed"
        if not state.is_in_duo:
            return None, "the tab left Duo"
        host = host_of(page.url)
        if host is None or not is_duo_host(host):
            return None, "the tab's top-level page isn't on Duo (embedded Duo is never read)"
        if state.site is None:
            return None, "the prompt has no vetted site"
        if not self._sites.check_host(state.site).is_allowed:
            return None, f"{shown_site(state.site)} is not in [duo] code_relay_sites"
        return state.site, ""

    def _forget(self, page: Page, done: asyncio.Task[None]) -> None:
        # Only if no newer task for this tab has replaced it meanwhile.
        if self._tasks.get(page) is done:
            del self._tasks[page]

    async def _relay(self, page: Page, state: TabDuoState) -> None:
        """Find the code and hand it on; a failure is logged, never raised."""
        try:
            found = await self._find_code(page, state)
            if found is not None:
                site, code = found
                self._on_code(page, site, code)
        except Exception as error:  # noqa: BLE001 - a background task has no caller to tell
            log_failure(logger, "Duo code relay", error)

    async def _find_code(self, page: Page, state: TabDuoState) -> tuple[str, str] | None:
        """(site, code), or None if no code showed on a qualifying page within the timeout."""
        try:
            async with asyncio.timeout(self._timeout_s):
                return await self._poll(page, state)
        except TimeoutError:
            logger.info("No Duo verification code found within %.0f s", self._timeout_s)
            return None

    async def _poll(self, page: Page, state: TabDuoState) -> tuple[str, str] | None:
        """Read the Duo frames until a code shows; None once the tab stops qualifying."""
        while self._relay_site(page, state) is not None:
            document_id = await _document_id(page)
            code = await read_verification_code(page)
            if code is not None:
                return await self._checked(page, state, code, document_id)
            await asyncio.sleep(self._interval_s)
        return None

    async def _checked(
        self, page: Page, state: TabDuoState, code: str, document_id: float | None
    ) -> tuple[str, str] | None:
        """(site, code) if the tab still qualifies right after the read, else None.

        `document_id` is the top-level document's id from just before the read.
        """
        if not await _is_fresh_navigation(page):
            logger.info("Duo code not relayed: the Duo page came from back/forward history")
            return None
        # Read after the history check, so the code and that check are both on this document.
        if document_id is None or await _document_id(page) != document_id:
            logger.info("Duo code not relayed: the tab changed documents while it was read")
            return None
        # Judged again with no await before handing on: the tab may have moved meanwhile.
        site = self._relay_site(page, state)
        return (site, code) if site is not None else None


async def _is_fresh_navigation(page: Page) -> bool:
    """True when the top-level document came from an ordinary navigation; False if unknown.

    History navigations replay the original request, so DuoWatch's request check
    alone can't tell them apart; the Navigation Timing entry can.
    """
    try:
        navigation_type = await page.main_frame.evaluate(_NAVIGATION_TYPE_JS)
    except PlaywrightError:
        return False
    return navigation_type == FRESH_NAVIGATION_TYPE


async def _document_id(page: Page) -> float | None:
    """The top-level document's performance.timeOrigin, or None if it can't be read."""
    try:
        return await page.main_frame.evaluate(_DOCUMENT_ID_JS)
    except PlaywrightError:
        return None
