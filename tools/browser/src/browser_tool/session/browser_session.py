"""The browser's lifecycle: lazy launch, the current tab, tab switching and shutdown.

The browser starts on the first tool call that needs it, not when the MCP server
starts, so registering the server doesn't pop a window. If the owner closes the
browser window, the next tool call launches it again, unless the session was made
with allow_relaunch=False (visit mode): then every start() after a close raises
BrowserClosedError, so a relaunched Edge without the run's login never acts. Every
context it opens gets the request guard, the Duo watcher (browser_tool.duo), the
dialog watch, the file-picker interception (dialogs/) and the PDF-to-download
rule (pdf_downloads). With a cookie mode, the saved cookies come back at launch
and (desktop only) are saved again on a clean close (browser_tool.cookie_store).

Where Edge runs is the backend's business (browser_tool.backends): the desktop
profile by default, or a docker job. Downloads are saved (browser_tool.downloads)
only for a backend that accepts them. Closing the context, or the context closing
by itself (the window closed, the browser crashed, the connection dropped),
also ends the backend's job.
"""

import asyncio
import logging
import re

from playwright.async_api import BrowserContext, Page, Playwright, async_playwright

from browser_tool.backends import Backend, LocalBackend
from browser_tool.config import Settings, resolve_tool_path
from browser_tool.cookie_store import CookieKeeper, CookieMode
from browser_tool.downloads import DownloadRecorder
from browser_tool.duo import DuoWatch
from browser_tool.errors import ActionError
from browser_tool.policy import HostPolicy
from browser_tool.redaction import register_sensitive_engine
from browser_tool.session.debug_env import clear_debug_env
from browser_tool.session.dialogs import DialogWatch, FileChooserWatch
from browser_tool.session.login_loop import LoginLoopGuard
from browser_tool.session.pdf_downloads import PdfDownloads
from browser_tool.session.request_guard import BlockLog, install_request_guard

logger = logging.getLogger(__name__)

MS_PER_SECOND = 1000
BROWSER_CLOSED = "the browser was closed, and this run doesn't relaunch it"


class BrowserClosedError(ActionError):
    """start() after a close, on a session that may not relaunch. The message is safe."""


class BrowserSession:
    """Owns the Playwright instance, the persistent context and the current page."""

    def __init__(
        self,
        settings: Settings,
        policy: HostPolicy,
        backend: Backend | None = None,
        *,
        allow_relaunch: bool = True,
        holds_dialogs: bool = True,
        cookie_mode: CookieMode | None = None,
    ):
        """Create an idle session; nothing launches until start() or current_page().

        Args:
            settings: The tool's settings.
            policy: The host policy every request is checked against.
            backend: Where Edge runs (default: the desktop profile, LocalBackend).
            allow_relaunch: False makes start() raise BrowserClosedError once any
                context has closed (the window, a crash, a dropped connection or
                close()), instead of launching a fresh Edge.
            holds_dialogs: False dismisses every page dialog instead of holding
                it for answer_dialog (visit mode has no model to answer).
            cookie_mode: How this browser uses [browser] cookie_file: OWN (the
                desktop server), BORROW (visit mode) or None (never touched).

        Raises:
            ValueError: If a [duo] code_relay_sites pattern is malformed (see DuoWatch).
        """
        self._settings = settings
        self._policy = policy
        self._backend = backend or LocalBackend(settings)
        self.block_log = BlockLog()
        # Follows every tab for Duo prompts; actions and the tool runner read it.
        self.duo = DuoWatch(settings.duo, job_label=lambda: self._backend.job_label)
        # Saves downloads, for backends that accept them (the desktop browser).
        self.downloads = DownloadRecorder(settings.downloads, policy)
        # Refuses a third fill_login on a site within 10 minutes (actions read it).
        self.login_loop = LoginLoopGuard()
        # Holds each tab's confirm/prompt/beforeunload dialog for answer_dialog.
        self.dialogs = DialogWatch(holds_dialogs=holds_dialogs)
        # Keeps native file pickers from opening; upload_file claims them.
        self.file_choosers = FileChooserWatch()
        # Every PDF response becomes a download, never Edge's viewer (pdf_downloads).
        self._pdf_downloads = PdfDownloads()
        self._cookies: CookieKeeper | None = None
        if cookie_mode is not None:
            cookie_file = resolve_tool_path(settings.browser.cookie_file)
            self._cookies = CookieKeeper(cookie_file, policy, cookie_mode)
        self._playwright: Playwright | None = None
        self._context: BrowserContext | None = None
        self._current: Page | None = None
        self._start_lock = asyncio.Lock()
        self._allow_relaunch = allow_relaunch
        self._has_closed = False

    @property
    def is_started(self) -> bool:
        """True while a browser context is open."""
        return self._context is not None

    @property
    def job_label(self) -> str | None:
        """The backend's job name for owner dialogs, e.g. "docker job 1a2b3c" (None locally)."""
        return self._backend.job_label

    @property
    def idle_close_s(self) -> float | None:
        """Seconds without a tool call after which the server closes this session, or None."""
        return self._backend.idle_close_s

    async def start(self) -> None:
        """Launch the browser if it isn't running. Safe to call repeatedly.

        Raises:
            BrowserClosedError: If a context has closed and relaunching is off.
            playwright.async_api.Error: If the browser can't launch.
            ValueError: If the profile's Preferences file is corrupt.
        """
        async with self._start_lock:
            if self._context is not None:
                return
            if self._has_closed and not self._allow_relaunch:
                raise BrowserClosedError(BROWSER_CLOSED)
            await self._stop_playwright()
            clear_debug_env()
            playwright = await async_playwright().start()
            try:
                self._context = await self._open_context(playwright)
            except BaseException:
                self._backend.close()
                await playwright.stop()
                raise
            self._playwright = playwright

    async def current_page(self) -> Page:
        """Return the current tab, launching the browser or opening a tab if needed."""
        await self.start()
        assert self._context is not None
        if self._current is None or self._current.is_closed():
            open_pages = self._context.pages
            self._current = open_pages[-1] if open_pages else await self._context.new_page()
        return self._current

    def pages(self) -> list[Page]:
        """All open tabs in order (empty before launch)."""
        return list(self._context.pages) if self._context is not None else []

    def current_or_none(self) -> Page | None:
        """The current tab if the browser is running and the tab is open, else None."""
        if self._current is not None and not self._current.is_closed():
            return self._current
        return None

    async def select_page(self, index: int) -> Page:
        """Make tab `index` current and bring it to the front.

        Raises:
            IndexError: If there is no such tab.
        """
        open_pages = self.pages()
        if not 0 <= index < len(open_pages):
            raise IndexError(f"no tab {index}; there are {len(open_pages)} tabs")
        self._current = open_pages[index]
        await self._current.bring_to_front()
        return self._current

    async def clear_cookies(self, domain_pattern: re.Pattern[str]) -> None:
        r"""Delete every cookie whose domain matches domain_pattern, launching if needed.

        A regex, because a cookie's domain is its host ("cas.example.edu") or a
        parent with a leading dot (".example.edu"), and one exact string matches
        only one of them. Pass e.g. re.compile(r"(^|\.)example\.edu$").

        Raises:
            BrowserClosedError: If a context has closed and relaunching is off.
            playwright.async_api.Error: If the browser can't launch or the clear fails.
        """
        await self.start()
        assert self._context is not None
        await self._context.clear_cookies(domain=domain_pattern)

    async def close(self) -> None:
        """Close the browser, end the backend's job and stop Playwright. Safe when not started."""
        async with self._start_lock:
            context, self._context, self._current = self._context, None, None
            if context is not None:
                self._has_closed = True
            try:
                if context is not None:
                    if self._cookies is not None:
                        await self._cookies.save(context)  # never raises
                    await context.close()
            finally:
                self._backend.close()
                await self._stop_playwright()

    async def end_stale_job(self) -> None:
        """Close the browser if the backend says its job must end (call before each tool call).

        The next tool call then starts a fresh one.
        """
        if self._context is not None and await self._backend.is_job_stale():
            await self.close()

    async def _open_context(self, playwright: Playwright) -> BrowserContext:
        context = await self._backend.open_context(playwright, self._policy)
        # After the context exists: Playwright sends a selector engine only to
        # contexts it creates or already tracks, and a CDP-connected default
        # context is neither until the connect returns.
        await register_sensitive_engine(playwright)
        browser = self._settings.browser
        context.set_default_timeout(browser.action_timeout_s * MS_PER_SECOND)
        context.set_default_navigation_timeout(browser.navigation_timeout_s * MS_PER_SECOND)
        await install_request_guard(context, self._policy, self.block_log)
        await self._pdf_downloads.watch(context)
        self.duo.watch(context)
        self.dialogs.watch(context)
        self.file_choosers.watch(context)
        if self._backend.downloads_incoming is not None:
            self.downloads.watch(context, self._backend.downloads_incoming)
        if self._cookies is not None:
            # Before any tool call can navigate: the launch tab is still blank.
            await self._cookies.restore(context)  # never raises
        context.on("close", self._on_context_closed)
        return context

    def _on_context_closed(self, context: BrowserContext) -> None:
        # The owner closed the window, the browser crashed or its connection dropped.
        # Relaunch on next use; Playwright itself is stopped then, since this handler
        # can't await. An explicit close() has already let go of the context.
        if context is not self._context:
            return
        logger.info("browser closed; it relaunches on the next tool call if allowed")
        self._has_closed = True
        self._context = None
        self._current = None
        # Never blocks: for docker it only starts `docker rm -f`.
        self._backend.close()

    async def _stop_playwright(self) -> None:
        playwright, self._playwright = self._playwright, None
        if playwright is not None:
            await playwright.stop()
