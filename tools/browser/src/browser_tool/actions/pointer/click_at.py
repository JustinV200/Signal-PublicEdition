"""The click_at tool: click a point on the screen, for canvases and elements a snapshot can't name.

It finds the deepest element at the point, through open shadow roots and into
iframes (each frame checked like a ref's: a blocked one is refused, an opaque
one is an unverified frame), and gates the click on that element exactly as a
click by ref (gating.click_gate_check, without scrolling, since the point is
fixed on screen). If it can't see into a frame there (or frames nest deeper
than MAX_FRAME_DEPTH), it gates on the <iframe> element with the
unverified-frame rule. The mouse moves to the point first and hover effects
get a moment to settle (target.hover_settle_gate), so a hover that swaps in
another element (or text) is judged as it will be clicked. Right before the
click it looks again: it refuses if another element is at the point by then,
or if the click rules on it now ask more than was approved
(gating.ensure_not_stricter); the page may have changed while the owner
decided. Then it runs the last-moment check (after_action.act_and_report) and
clicks that element at the point's offset inside it, so Playwright's
hit-target check still applies. A page that changes the element on
pointerdown, or in the last tens of ms, isn't caught, and a page can always
send from an innocent label's onclick (README, Known gaps).
"""

import math

from playwright.async_api import ElementHandle, Frame, Page
from playwright.async_api import Error as PlaywrightError

from browser_tool.actions.context import ActionContext
from browser_tool.actions.errors import ActionError
from browser_tool.actions.gating import (
    GatedAction,
    click_gate_check,
    confirm_or_log,
    ensure_not_stricter,
)
from browser_tool.actions.guards import ensure_ready_to_act, frame_check
from browser_tool.actions.pointer.after_action import act_and_report
from browser_tool.actions.pointer.target import hover_settle_gate, prepare_page
from browser_tool.actions.untrusted import wrap_untrusted
from browser_tool.gates import GateCheck

MAX_FRAME_DEPTH = 5
UNREADABLE_FRAME = "a frame the tool can't see into"
NOTHING_THERE = "refused: nothing at that point; use coordinates inside the viewport"
PAGE_CHANGED = "refused: the page changed under that point; take a new screenshot or snapshot"
# The deepest element at the point in one document, through open shadow roots.
POINT_JS = """([x, y]) => {
  let el = document.elementFromPoint(x, y);
  while (el && el.shadowRoot) {
    const inner = el.shadowRoot.elementFromPoint(x, y);
    if (!inner || inner === el) break;
    el = inner;
  }
  return el;
}"""
IS_FRAME_JS = "(el) => el.tagName === 'IFRAME' || el.tagName === 'FRAME'"
# Where a frame's document starts, in its parent's viewport (border and padding).
FRAME_OFFSET_JS = """(f) => {
  const box = f.getBoundingClientRect();
  const style = getComputedStyle(f);
  return [box.left + f.clientLeft + parseFloat(style.paddingLeft),
    box.top + f.clientTop + parseFloat(style.paddingTop)];
}"""
# A short name for the dialog and the result (page-supplied).
NAME_JS = """(el) => (el.getAttribute('aria-label') || el.innerText || el.tagName.toLowerCase())
  .replace(/\\s+/g, ' ').trim().slice(0, 80)"""
SAME_JS = "(el, other) => el === other"


async def click_at(ctx: ActionContext, x: float, y: float) -> str:
    """Click at viewport point (x, y) in CSS pixels, asking the owner if sensitive.

    Raises:
        ActionError: For a point off the page, an element in a blocked frame, a
            declined click, or a page that changed under the point meanwhile.
    """
    if not (math.isfinite(x) and math.isfinite(y)):
        raise ActionError("bad point: x and y must be numbers")
    page = await prepare_page(ctx)

    async def find_and_judge() -> tuple[ElementHandle, str | None, GateCheck | None]:
        element, frame_origin = await element_at(ctx, page, x, y)
        return element, frame_origin, await _judge(ctx, element, frame_origin)

    # Hover first: a hover effect can swap what is at the point, and the click
    # would move the mouse there anyway. Then judge what the hover left there.
    element, frame_origin, check = await hover_settle_gate(
        page, lambda: page.mouse.move(x, y), find_and_judge
    )
    try:
        name = await element.evaluate(NAME_JS)
        point = f"({x:g}, {y:g})"
        action = GatedAction(f"click at {point} on {name}", f"click_at {point}", frame_origin)
        approved_origin = await confirm_or_log(ctx, page, action, check)
        ensure_ready_to_act(ctx, page, approved_origin)  # a moved tab is refused as such
        await _ensure_still_there(ctx, page, x, y, element)
        # The same element may have changed meanwhile (new text, a new handler).
        ensure_not_stricter(check, await _judge(ctx, element, frame_origin))
        offset = await _offset_in(element, x, y)
        # Clicking the element itself (not the mouse) keeps Playwright's hit-target
        # check: if something else is at the point by then, the click doesn't land.
        return await act_and_report(
            ctx,
            page,
            approved_origin,
            lambda: element.click(position=offset),
            f"clicked at {point} on {wrap_untrusted(name)}",
            trigger=[name],
        )
    finally:
        await element.dispose()


async def _judge(
    ctx: ActionContext, element: ElementHandle, frame_origin: str | None
) -> GateCheck | None:
    """The click rules on the element at the point, without scrolling (the point is fixed)."""
    return await click_gate_check(ctx, element, "", frame_origin, scroll_first=False)


async def _offset_in(element: ElementHandle, x: float, y: float) -> dict[str, float]:
    """Viewport point (x, y) as an offset inside the element's box (for click(position=)).

    Raises:
        ActionError: If the element has no box any more.
    """
    box = await element.bounding_box()
    if box is None:
        raise ActionError(PAGE_CHANGED)
    return {"x": x - box["x"], "y": y - box["y"]}


async def element_at(
    ctx: ActionContext, page: Page, x: float, y: float
) -> tuple[ElementHandle, str | None]:
    """The deepest element at viewport point (x, y), through shadow roots and iframes.

    Also used by click to hit-test a double click's second half.

    Returns:
        The element, and its frame origin when that frame is unverified.

    Raises:
        ActionError: If nothing is there, or the point is in a blocked frame.
    """
    element = await _point_in(page.main_frame, x, y)
    frame_origin = None
    for _ in range(MAX_FRAME_DEPTH):
        if not await element.evaluate(IS_FRAME_JS):
            return element, frame_origin
        inner = await element.content_frame()
        if inner is None:
            return element, UNREADABLE_FRAME
        # Every frame on the way is checked: a blocked one is refused even inside an opaque one.
        inner_origin = frame_check(ctx, page, inner)
        frame_origin = frame_origin or inner_origin
        try:
            left, top = await element.evaluate(FRAME_OFFSET_JS)
            inner_element = await _point_in(inner, x - left, y - top)
        except (PlaywrightError, ActionError):
            return element, UNREADABLE_FRAME
        await element.dispose()
        element, x, y = inner_element, x - left, y - top
    # Frames nest deeper than MAX_FRAME_DEPTH: gate on what is there as unverified.
    return element, UNREADABLE_FRAME


async def _point_in(frame: Frame, x: float, y: float) -> ElementHandle:
    """The deepest element at (x, y) in `frame`'s own viewport.

    Raises:
        ActionError: If nothing is there (off the viewport).
    """
    handle = await frame.evaluate_handle(POINT_JS, [x, y])
    element = handle.as_element()
    if element is None:
        await handle.dispose()
        raise ActionError(NOTHING_THERE)
    return element


async def _ensure_still_there(
    ctx: ActionContext, page: Page, x: float, y: float, element: ElementHandle
) -> None:
    """Refuse if the element at the point is no longer the one the gate judged.

    Raises:
        ActionError: If another element (or nothing) is there now.
    """
    now, _ = await element_at(ctx, page, x, y)
    try:
        is_same = await element.evaluate(SAME_JS, now)
    except PlaywrightError:  # a handle from another frame: not the same element
        is_same = False
    finally:
        await now.dispose()
    if not is_same:
        raise ActionError(PAGE_CHANGED)
