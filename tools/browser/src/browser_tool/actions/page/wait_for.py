"""The wait_for tool: wait, read only, until the page shows what the model is waiting for.

Conditions (all given ones must hold): text in the page's snapshot, an
element (by ref) gone, the URL containing a string, or the network idle. Text
is matched against fresh snapshots (snapshot.take_snapshot, polled), which are
redacted and scrubbed of every tab's secrets, never against the live DOM: a
live match would be a yes/no oracle on a secret mirrored into page text. The
URL is matched, polled too, as the model sees it (secret_scrub.shown_url: no
query or fragment, the path decoded, scrubbed the same way), so the wait can't probe a query
string's tokens or a secret a script put in the path. It answers only met or
not met, never page text, and its result is scrubbed too. Like every read tool
it refuses first a tab in Duo, then a page off the allowlist, then a page the
vault reports filled. When the wait ends, met or not, navigate's landing
backstop runs (signin.report_location), so a landing on a blocked origin is
cleared and a login page gets the signed-out note.
"""

import asyncio
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from playwright.async_api import Error as PlaywrightError
from playwright.async_api import Page
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from browser_tool.actions.context import ActionContext
from browser_tool.actions.errors import ActionError
from browser_tool.actions.guards import (
    ensure_no_filled_credentials,
    ensure_not_in_duo,
    ensure_page_allowed,
    ensure_ref_format,
)
from browser_tool.actions.page.snapshot import take_snapshot
from browser_tool.actions.secret_scrub import scrub_or_refuse, shown_url
from browser_tool.actions.signin import report_location

DEFAULT_WAIT_S = 10.0
MAX_WAIT_S = 30.0
MAX_CONDITION_CHARS = 200
MS_PER_SECOND = 1000
BAD_TIMEOUT = "bad timeout_s: use a number of seconds above 0 (at most 30)"
NO_CONDITION = "bad wait: give text, gone_ref, url_contains or network_idle=true"
BAD_TEXT = "bad {name}: use 1 to 200 characters"
TIMED_OUT = "still waiting after {wait_s:g} s for: {unmet}"
RETRY_HINT = "call wait_for again or take a snapshot()"
# How often the text and URL conditions look again (text: a fresh snapshot).
POLL_S = 0.25
TAB_CLOSED = "the tab closed; use tabs() and switch_tab()"


async def wait_for(
    ctx: ActionContext,
    text: str | None = None,
    gone_ref: str | None = None,
    url_contains: str | None = None,
    network_idle: bool = False,
    timeout_s: float = DEFAULT_WAIT_S,
) -> str:
    """Wait until every given condition holds on the current tab, for up to timeout_s (max 30).

    Args:
        ctx: The action context.
        text: Text the page's scrubbed snapshot must contain (any case).
        gone_ref: A snapshot ref whose element must be gone or hidden.
        url_contains: A string the URL (without query or fragment) must contain.
        network_idle: Wait for no network traffic for 500 ms.
        timeout_s: Seconds to wait, capped at MAX_WAIT_S.

    Returns:
        "waited N s for: <conditions>; now at <url>" or "still waiting after N s
        for: <unmet>; now at <url>" (both plus block and signed-out notes), or
        TAB_CLOSED.

    Raises:
        ActionError: On bad arguments, a refused page, or a landing the policy blocks.
    """
    wait_s = _checked_wait(timeout_s)
    for name, value in (("text", text), ("url_contains", url_contains)):
        if value is not None and not 0 < len(value) <= MAX_CONDITION_CHARS:
            raise ActionError(BAD_TEXT.format(name=name))
    if gone_ref is not None:
        ensure_ref_format(gone_ref)
    page = await ctx.session.current_page()
    ensure_not_in_duo(ctx, page)
    ensure_page_allowed(ctx, page)
    await ensure_no_filled_credentials(ctx, page)
    wanted = _Wanted(text, gone_ref, url_contains, network_idle)
    conditions = _conditions(ctx, page, wait_s, wanted)
    if not conditions:
        raise ActionError(NO_CONDITION)
    ctx.session.block_log.drain()
    started = time.monotonic()
    results = await _run_all([waiting for _name, waiting in conditions])
    unmet = [name for (name, _waiting), held in zip(conditions, results, strict=True) if not held]
    if page.is_closed():
        return TAB_CLOSED
    if unmet:
        timed_out = TIMED_OUT.format(wait_s=wait_s, unmet=", ".join(unmet))
        result = await report_location(ctx, page, f"{timed_out}; now at") + f"; {RETRY_HINT}"
    else:
        waited_s = time.monotonic() - started
        met = ", ".join(name for name, _waiting in conditions)
        result = await report_location(ctx, page, f"waited {waited_s:.1f} s for: {met}; now at")
    [scrubbed] = await scrub_or_refuse(ctx, [result])
    return scrubbed


async def _run_all(waits: list[Awaitable[bool]]) -> list[bool]:
    """Run the condition waits together; if one raises, cancel the rest so none lingers."""
    tasks = [asyncio.ensure_future(waiting) for waiting in waits]
    try:
        return await asyncio.gather(*tasks)
    finally:
        for task in tasks:
            task.cancel()
        # Let the cancelled ones finish, so none is left pending or unretrieved.
        await asyncio.gather(*tasks, return_exceptions=True)


def _checked_wait(timeout_s: float) -> float:
    """timeout_s capped at MAX_WAIT_S. Raises ActionError if it isn't above 0 (NaN too)."""
    if not timeout_s > 0:
        raise ActionError(BAD_TIMEOUT)
    return min(timeout_s, MAX_WAIT_S)


@dataclass(frozen=True)
class _Wanted:
    """The conditions the model asked for (None or False: not asked)."""

    text: str | None
    gone_ref: str | None
    url_contains: str | None
    network_idle: bool


def _conditions(
    ctx: ActionContext, page: Page, wait_s: float, wanted: _Wanted
) -> list[tuple[str, Awaitable[bool]]]:
    """The (name, wait) pairs for the asked conditions; each is read only and says if it held."""
    timeout_ms = wait_s * MS_PER_SECOND
    conditions: list[tuple[str, Awaitable[bool]]] = []
    if wanted.text is not None:
        needle = wanted.text.casefold()

        async def has_text() -> bool:
            return needle in (await take_snapshot(ctx, page)).text.casefold()

        conditions.append(("text", _poll(ctx, page, wait_s, has_text)))
    if wanted.gone_ref is not None:
        # Detached or hidden both count; a ref that is already gone holds at once.
        gone = page.get_by_ref(wanted.gone_ref).wait_for(state="hidden", timeout=timeout_ms)
        conditions.append(("gone_ref", _holds(gone)))
    if wanted.url_contains is not None:
        part = wanted.url_contains

        async def has_url() -> bool:
            return part in await shown_url(ctx, page.url)

        conditions.append(("url_contains", _poll(ctx, page, wait_s, has_url)))
    if wanted.network_idle:
        idle = page.wait_for_load_state("networkidle", timeout=timeout_ms)
        conditions.append(("network_idle", _holds(idle)))
    return conditions


async def _poll(
    ctx: ActionContext, page: Page, wait_s: float, check: Callable[[], Awaitable[bool]]
) -> bool:
    """True once check() is, polled every POLL_S within wait_s; False on timeout, a
    closed tab, or a tab that moved to an origin the policy doesn't allow (the
    caller's report_location then clears it; nothing is read from that page).

    Raises:
        ActionError: If a scrub fails (nothing is ever matched unscrubbed).
    """
    deadline = time.monotonic() + wait_s
    while not page.is_closed():
        if not ctx.policy.check_url(page.url).is_allowed:
            return False
        try:
            if await check():
                return True
        except PlaywrightError:
            pass  # e.g. a navigation replaced the document mid-snapshot: look again
        remaining_s = deadline - time.monotonic()
        if remaining_s <= 0:
            return False
        await asyncio.sleep(min(POLL_S, remaining_s))
    return False


async def _holds(waiting: Awaitable[None]) -> bool:
    """True when the wait finished; False when it timed out or the tab closed meanwhile."""
    try:
        await waiting
    except PlaywrightTimeoutError:
        return False
    except PlaywrightError as error:
        # The only other expected failure is a tab that closed; the caller checks.
        if "has been closed" not in str(error):
            raise
        return False
    return True
