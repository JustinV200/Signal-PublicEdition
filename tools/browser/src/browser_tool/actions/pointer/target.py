"""The shared prelude of the pointer, field and key tools: which tab and element they act on.

prepare_page fetches the current tab and refuses a tab in Duo (owner-only),
then one on a non-allowed origin, in that order. prepare_ref also resolves a
snapshot ref to one element, its snapshot label and its frame check (a blocked
frame is refused, an opaque one is returned for the gate rules to log).
hover_settle_gate puts the mouse where a click will land and lets hover
effects settle before the click rules judge the element, so a hover that
swaps in a "Send" button is judged as "Send" (click and click_at).
"""

from collections.abc import Awaitable, Callable
from typing import NamedTuple

from playwright.async_api import Locator, Page

from browser_tool.actions.context import ActionContext
from browser_tool.actions.guards import (
    ensure_not_in_duo,
    ensure_page_allowed,
    frame_mismatch_origin,
    resolve_ref,
)

# How long hover effects get before the click rules judge the element. A page
# that changes it later than this, or on pointerdown, isn't caught (see the
# README's Known gaps).
HOVER_SETTLE_MS = 300


class RefTarget(NamedTuple):
    """An element a tool acts on.

    Attributes:
        page: Its tab.
        locator: The element.
        label: Its snapshot label, e.g. 'button "Send"' (page-supplied).
        frame_origin: Its frame's origin when that frame is unverified, else None.
    """

    page: Page
    locator: Locator
    label: str
    frame_origin: str | None


async def prepare_page(ctx: ActionContext) -> Page:
    """The current tab, after the Duo lockout and then the origin check.

    Raises:
        ActionError: If the tab is in Duo or on a non-allowed origin.
    """
    page = await ctx.session.current_page()
    ensure_not_in_duo(ctx, page)
    ensure_page_allowed(ctx, page)
    return page


async def prepare_ref(ctx: ActionContext, ref: str) -> RefTarget:
    """prepare_page, then the element `ref` from the latest snapshot and its frame check.

    Raises:
        ActionError: As prepare_page, or if the ref is stale or malformed, or
            the element is in a blocked frame.
    """
    page = await prepare_page(ctx)
    locator = await resolve_ref(page, ref)
    label = ctx.ref_labels.label_for(page, ref)
    frame_origin = await frame_mismatch_origin(ctx, page, locator)
    return RefTarget(page, locator, label, frame_origin)


def log_target(tool: str, ref: str, label: str) -> str:
    """The target for log lines: tool, ref and role, never the page-supplied name."""
    return f"{tool} {ref} ({label.split(' ', 1)[0]})"


async def hover_settle_gate[GateResult](
    page: Page,
    hover: Callable[[], Awaitable[object]],
    gate: Callable[[], Awaitable[GateResult]],
) -> GateResult:
    """Hover where the click will land, wait HOVER_SETTLE_MS, then run the gate.

    Args:
        page: The tab.
        hover: Moves the mouse there, e.g. locator.hover or a mouse.move.
        gate: Finds and judges the element, after the hover settled.

    Returns:
        Whatever `gate` returns.
    """
    await hover()
    await page.wait_for_timeout(HOVER_SETTLE_MS)
    return await gate()
