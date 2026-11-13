"""The one login fill a visit may make: when it's allowed, and the fill and wait itself.

A fill is allowed only on [visit] login_host, only when the target's host is in
login_from_hosts, and only when the login URL's `service` parameter is exactly one
https URL on a login_from_hosts host, with no userinfo and no explicit port. So a
page that sent the tab to CAS by script, or for some other service, is never filled.
The raw page URL (query included) is read here and never goes into a result.

The fill goes through ToolRunner.run like every other action. After an "ok", the tab
is watched (duo.wait_until_off_duo: frame events, plus a poll every second) until it
leaves the login host and Duo, for up to login_wait_s (the vault's dialog, Windows
Hello and Duo all happen in that time).
"""

import logging
from enum import Enum
from urllib.parse import parse_qs, urlsplit

from mcp.server.mcpserver.exceptions import ToolError
from playwright.async_api import Page

from browser_tool import actions
from browser_tool.actions import ActionContext
from browser_tool.config import VisitSettings
from browser_tool.credentials import FILL_OK
from browser_tool.duo import WaitOutcome, is_duo_url, wait_until_off_duo
from browser_tool.policy import host_of
from browser_tool.server.tool_runner import ToolRunner

logger = logging.getLogger(__name__)

# The only scheme a `service` URL may have. Read as login.SERVICE_SCHEME at call
# time, so the fixture tests (plain http on *.localhost) can relax it.
SERVICE_SCHEME = "https"
# Read the same way; the fixture server serves on a port, so its tests allow one.
ALLOW_SERVICE_PORT = False
SERVICE_PARAM = "service"


class LoginOutcome(Enum):
    """How a fill and its wait ended."""

    DONE = "done"  # the tab left the login host and Duo
    FAILED = "failed"  # the fill wasn't ok, or the wait ran out
    CLOSED = "closed"  # the browser closed meanwhile


def is_fill_allowed(target_url: str, page_url: str, visit: VisitSettings) -> bool:
    """True if the tab, now on page_url after navigating to target_url, may be filled."""
    from_hosts = {host.lower() for host in visit.login_from_hosts}
    if not visit.login_host or host_of(page_url) != visit.login_host.lower():
        return False
    if host_of(target_url) not in from_hosts:
        return False
    try:
        query = parse_qs(urlsplit(page_url).query, keep_blank_values=True)
        services = query.get(SERVICE_PARAM, [])
        # Exactly one, blank ones counted: with two, which one CAS honours is its
        # choice, not ours.
        if len(services) != 1:
            return False
        service = urlsplit(services[0])
        has_userinfo = service.username is not None or service.password is not None
        # Any explicit port, even 443 or a bare ":", is refused: lms.example.edu:8443
        # is another service. .port raises ValueError on a non-numeric one.
        has_port = service.port is not None or service.netloc.endswith(":")
    except ValueError:
        return False
    is_secure = service.scheme == SERVICE_SCHEME
    is_port_ok = ALLOW_SERVICE_PORT or not has_port
    return is_secure and is_port_ok and not has_userinfo and host_of(services[0]) in from_hosts


async def log_in(runner: ToolRunner, ctx: ActionContext, visit: VisitSettings) -> LoginOutcome:
    """Fill login_credential with submit, then wait for the tab to leave the login host and Duo.

    The caller has checked is_fill_allowed and that no fill happened yet this run.
    A refused or failed fill (ToolError) is FAILED; its scrubbed text is logged.
    """
    try:
        text = await runner.run("fill_login", actions.fill_login, visit.login_credential, True)
    except ToolError as error:
        logger.warning("fill_login refused: %s", error)
        return LoginOutcome.FAILED
    # The runner may append a Duo notice after the fill's own first line.
    first_line = text.split("\n", 1)[0].strip()
    if first_line != FILL_OK:
        logger.warning("fill_login didn't fill: %s", first_line)
        return LoginOutcome.FAILED
    return await _wait_off_login(ctx, visit)


async def _wait_off_login(ctx: ActionContext, visit: VisitSettings) -> LoginOutcome:
    """Wait until the tab is off the login host and Duo, it closes, or login_wait_s runs out."""
    page = ctx.session.current_or_none()
    login_host = visit.login_host.lower()

    def is_on_login(tab: Page) -> bool:
        return host_of(tab.url) == login_host or is_duo_url(tab.url)

    outcome = WaitOutcome.CLOSED
    if page is not None:
        outcome = await wait_until_off_duo(page, visit.login_wait_s, is_on_login)
    if outcome is WaitOutcome.CLOSED:
        logger.warning("the browser closed during the login")
        return LoginOutcome.CLOSED
    if outcome is WaitOutcome.TIMEOUT:
        logger.warning("the login didn't finish within %s s", visit.login_wait_s)
        return LoginOutcome.FAILED
    return LoginOutcome.DONE
