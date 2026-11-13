"""Enforce the host policy on every request the browser context makes.

Layer 1, routing: context.route("**/*") aborts any request to a non-allowed host
or a non-network scheme such as file:.
This covers navigations, subresources, fetch/XHR and popups, but only the FIRST url
of a redirect chain (a Playwright limitation).

Layer 2, redirect hops: these are stopped at DNS level by --host-resolver-rules
(see browser_tool.policy.resolver_rules). The "request" listener here sees each
hop and records blocked ones, so the navigate tool can tell the model why its
navigation failed.

Logging is origin-only: never full URLs, headers or post data.
"""

import logging
from collections import deque
from dataclasses import dataclass

from playwright.async_api import BrowserContext, Request, Route
from playwright.async_api import Error as PlaywrightError

from browser_tool.policy import NETWORK_SCHEMES, OPAQUE_SCHEMES, HostPolicy, origin_of, scheme_of

logger = logging.getLogger(__name__)

MAX_RECORDED_BLOCKS = 50
ABORT_ERROR_CODE = "blockedbyclient"


@dataclass(frozen=True)
class BlockedRequest:
    """One blocked request: where it was going and why."""

    origin: str
    reason: str
    is_navigation: bool
    is_redirect: bool


class BlockLog:
    """Recent blocked requests, drained by actions that want to report them."""

    def __init__(self) -> None:
        """Create an empty log holding at most MAX_RECORDED_BLOCKS entries."""
        self._entries: deque[BlockedRequest] = deque(maxlen=MAX_RECORDED_BLOCKS)

    def record(self, entry: BlockedRequest) -> None:
        """Add one blocked request."""
        self._entries.append(entry)

    def drain(self) -> list[BlockedRequest]:
        """Return and clear everything recorded so far."""
        entries = list(self._entries)
        self._entries.clear()
        return entries


async def install_request_guard(
    context: BrowserContext, policy: HostPolicy, block_log: BlockLog
) -> None:
    """Install the routing handler and the redirect-hop listener on `context`."""

    async def handle_route(route: Route) -> None:
        await _route_request(route, policy, block_log)

    def handle_request(request: Request) -> None:
        _note_redirect_hop(request, policy, block_log)

    await context.route("**/*", handle_route)
    context.on("request", handle_request)


async def _route_request(route: Route, policy: HostPolicy, block_log: BlockLog) -> None:
    request = route.request
    url = request.url
    try:
        # data:/blob:/about: never leave the browser. Everything else is policed, so
        # file: and other non-network schemes are aborted as unsupported_scheme.
        if scheme_of(url) in OPAQUE_SCHEMES:
            await route.continue_()
            return
        decision = policy.check_url(url)
        if decision.is_allowed:
            if policy.is_allow_all and request.is_navigation_request():
                logger.info("allow-all mode: navigation to %s", origin_of(url))
            await route.continue_()
            return
        block_log.record(
            BlockedRequest(origin_of(url), decision.reason, request.is_navigation_request(), False)
        )
        logger.warning(
            "blocked %s request to %s (%s)", request.resource_type, origin_of(url), decision.reason
        )
        await route.abort(ABORT_ERROR_CODE)
    except PlaywrightError as error:
        # Usually the page closed mid-request. Log the type only: messages can hold URLs.
        logger.debug("route handling failed for %s: %s", origin_of(url), type(error).__name__)


def _note_redirect_hop(request: Request, policy: HostPolicy, block_log: BlockLog) -> None:
    if request.redirected_from is None or scheme_of(request.url) not in NETWORK_SCHEMES:
        return
    decision = policy.check_url(request.url)
    origin = origin_of(request.url)
    if decision.is_allowed:
        if policy.is_allow_all and request.is_navigation_request():
            logger.info("allow-all mode: redirect to %s", origin)
        return
    block_log.record(BlockedRequest(origin, decision.reason, request.is_navigation_request(), True))
    logger.warning("redirect hop to %s blocked (%s)", origin, decision.reason)
