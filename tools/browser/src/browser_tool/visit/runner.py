"""One visit launch: start Edge, visit each target in order, close Edge.

Every action goes through ToolRunner.run (navigate, snapshot, and fill_login on the
login host), so the policy, the scrubbing, the untrusted-content wrapping and the
Duo watcher all apply unchanged; only text run() returned reaches a PageResult.
There's no code path to click, type_text, press_key, select_option or screenshot.

Per target: navigate, wait for the network to settle (capped at settle_s), then
- on a [visit] signin_hosts host, or after a failed navigation whose last
  main-frame hop went there or to CAS: google_signin_needed, for this target and
  every later one;
- on the login host: the run's one fill when login.is_fill_allowed says so, then
  navigate again. A refused fill gives this target login_needed; a failed fill or
  wait gives it and every later target login_needed;
- otherwise: snapshot, and the target is ok.
A launch that can meet a Google sign-in (signin_hosts set) first clears every
school cookie (sso.py, from [visit] school_domain). The session never relaunches (allow_relaunch=False), so
after the window closes every remaining target gets error.
"""

import logging

from mcp.server.mcpserver.exceptions import ToolError
from playwright.async_api import Error as PlaywrightError

from browser_tool import actions
from browser_tool.actions import ActionContext
from browser_tool.config import VisitSettings
from browser_tool.policy import display_url, host_of
from browser_tool.server.tool_runner import ToolRunner
from browser_tool.visit import sso
from browser_tool.visit.hops import MainFrameHops
from browser_tool.visit.launch import start_browser
from browser_tool.visit.login import LoginOutcome, is_fill_allowed, log_in
from browser_tool.visit.plan import Target
from browser_tool.visit.result import (
    PAGE_ERROR,
    PAGE_GOOGLE_SIGNIN_NEEDED,
    PAGE_LOGIN_NEEDED,
    PAGE_OK,
    STATUS_OK,
    PageResult,
    VisitResult,
)

logger = logging.getLogger(__name__)

MS_PER_SECOND = 1000


async def run_visit(
    ctx: ActionContext, targets: tuple[Target, ...], visit: VisitSettings
) -> VisitResult:
    """Visit targets in one launch (see the module docstring); Edge is closed at the end.

    ctx must be built with allow_relaunch=False. A launch failure is a busy or error
    VisitResult with no pages.

    Raises:
        playwright.async_api.Error: If the cookie clear fails (the launch stops
            before any navigation).
    """
    status = await start_browser(ctx)
    if status != STATUS_OK:
        return VisitResult(status)
    try:
        visitor = _Visitor(ctx, visit)
        await visitor.prepare()
        pages = [await visitor.visit(target) for target in targets]
    finally:
        await ctx.session.close()
    return VisitResult(STATUS_OK, tuple(pages))


class _Visitor:
    """One launch's state: the runner, the hop record, the one fill, and a stop status."""

    def __init__(self, ctx: ActionContext, visit: VisitSettings):
        self._ctx = ctx
        self._visit = visit
        self._runner = ToolRunner(ctx)
        self._hops = MainFrameHops()
        self._signin_hosts = {host.lower() for host in visit.signin_hosts}
        self._login_host = visit.login_host.lower()
        self._sso_host = sso.sso_host_pattern(visit.sso_host)
        self._has_filled = False
        # Set once a target ends the launch's useful work: later targets get it too.
        self._stop_status: str | None = None

    async def prepare(self) -> None:
        """Clear the school cookies on a sign-in launch, and start recording hops."""
        if self._signin_hosts and self._visit.school_domain:
            await self._ctx.session.clear_cookies(
                sso.school_cookie_domain(self._visit.school_domain)
            )
        self._hops.attach(await self._ctx.session.current_page())

    async def visit(self, target: Target) -> PageResult:
        """One target's PageResult. A ToolError from an action never escapes."""
        if self._stop_status:
            return _page(target, self._stop_status)
        try:
            status = await self._open(target)
            if status != PAGE_OK:
                return _page(target, status)
            text = await self._runner.run("snapshot", actions.snapshot)
        except ToolError as error:
            # Already scrubbed by the runner, so safe to log.
            logger.warning("target %s failed: %s", target.key, error)
            return _page(target, self._failure_status())
        return _page(target, PAGE_OK, text)

    async def _open(self, target: Target) -> str:
        """Navigate to target and deal with sign-in and login pages; PAGE_OK if it's readable."""
        await self._navigate(target.url)
        host = self._page_host()
        if host in self._signin_hosts:
            return self._stop(PAGE_GOOGLE_SIGNIN_NEEDED)
        if not self._login_host or host != self._login_host:
            return PAGE_OK
        if self._has_filled:
            # Back on the login page after the run's one fill: it didn't hold.
            return self._stop(PAGE_LOGIN_NEEDED)
        if not is_fill_allowed(target.url, self._page_url(), self._visit):
            logger.warning("target %s reached the login host but may not be filled", target.key)
            return PAGE_LOGIN_NEEDED
        self._has_filled = True
        outcome = await log_in(self._runner, self._ctx, self._visit)
        if outcome is LoginOutcome.CLOSED:
            return PAGE_ERROR
        if outcome is LoginOutcome.FAILED:
            return self._stop(PAGE_LOGIN_NEEDED)
        await self._navigate(target.url)
        return self._stop(PAGE_LOGIN_NEEDED) if self._page_host() == self._login_host else PAGE_OK

    async def _navigate(self, url: str) -> None:
        """navigate through the runner, then let the page settle. Raises ToolError."""
        self._hops.reset()
        await self._runner.run("navigate", actions.navigate, url)
        page = self._ctx.session.current_or_none()
        if page is None:
            return
        try:
            # Classroom renders client-side, so wait for quiet, but never past settle_s.
            timeout_ms = self._visit.settle_s * MS_PER_SECOND
            await page.wait_for_load_state("networkidle", timeout=timeout_ms)
        except PlaywrightError as error:
            logger.debug("the page didn't settle: %s", type(error).__name__)

    def _failure_status(self) -> str:
        """A failed action's status: google_signin_needed if a sign-in launch's last hop
        went to a sign-in host or CAS, else error."""
        last_hop = self._hops.last_host
        is_signin_hop = last_hop in self._signin_hosts or bool(self._sso_host.search(last_hop))
        if self._signin_hosts and last_hop and is_signin_hop:
            return self._stop(PAGE_GOOGLE_SIGNIN_NEEDED)
        return PAGE_ERROR

    def _stop(self, status: str) -> str:
        """Give status to this target and every later one."""
        self._stop_status = status
        return status

    def _page_url(self) -> str:
        """The tab's raw URL (query included), or "". Never put into a result."""
        page = self._ctx.session.current_or_none()
        return page.url if page is not None else ""

    def _page_host(self) -> str:
        """The tab's host, lower-cased, or ""."""
        return host_of(self._page_url()) or ""


def _page(target: Target, status: str, text: str = "") -> PageResult:
    """A PageResult for target, with its display URL (no query string)."""
    return PageResult(key=target.key, status=status, url=display_url(target.url), text=text)
