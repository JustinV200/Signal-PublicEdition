"""The log-only pointer tools: hover and scroll.

Neither ever asks the owner, but both run the same checks as a click: the Duo
lockout first, the origin check, the frame check for a ref (a blocked frame is
refused), and ensure_ready_to_act right before the page is touched (through
after_action.act_checked, which stops waiting if the page opens a dialog). What they
touch is logged when a gate rule matches it (gating.log_only), never with page
text. scroll moves the nearest scrollable box (the ref, an ancestor of it, or
the page) by screens, and reports where it is and whether the content grew
(an infinite list loading more when the end was reached).
"""

from playwright.async_api import Locator

from browser_tool.actions.context import ActionContext
from browser_tool.actions.errors import ActionError
from browser_tool.actions.gating import GatedAction, confirm_or_log, gate_check, log_only
from browser_tool.actions.pointer.after_action import DIALOG_OPENED_NOTE, act_checked
from browser_tool.actions.pointer.target import log_target, prepare_page, prepare_ref
from browser_tool.actions.untrusted import wrap_untrusted

# Direction -> (x, y) unit step.
DIRECTIONS = {"down": (0, 1), "up": (0, -1), "right": (1, 0), "left": (-1, 0)}
MAX_SCREENS = 10.0
# How long scroll waits for more content after it reached the end.
GROW_WAIT_MS = 1000
# The nearest box that can scroll along the axis: el, an ancestor, else the page.
SCROLLER_JS = """(el, vertical) => {
  const canScroll = (n) => {
    const overflow = getComputedStyle(n)[vertical ? 'overflowY' : 'overflowX'];
    const room = vertical ? n.scrollHeight > n.clientHeight : n.scrollWidth > n.clientWidth;
    return room && /auto|scroll|overlay/.test(overflow);
  };
  const page = [document.body, document.documentElement];
  for (let n = el; n && !page.includes(n); n = n.parentElement) {
    if (canScroll(n)) return n;
  }
  return document.scrollingElement;
}"""
# Scroll the box by screens; return [position, size, view] along the axis afterwards.
SCROLL_JS = """(box, [dx, dy, screens]) => {
  box.scrollBy({left: dx * box.clientWidth * screens, top: dy * box.clientHeight * screens,
    behavior: 'instant'});
  return dy ? [box.scrollTop, box.scrollHeight, box.clientHeight]
    : [box.scrollLeft, box.scrollWidth, box.clientWidth];
}"""
# Resolve with the box's size along the axis once it grows past `size`, or after `ms`.
# setTimeout, not requestAnimationFrame, which a background tab pauses.
GROW_WAIT_JS = """(box, [vertical, size, ms]) => new Promise((resolve) => {
  const start = performance.now();
  const tick = () => {
    const now = vertical ? box.scrollHeight : box.scrollWidth;
    if (now > size || performance.now() - start > ms) resolve(now); else setTimeout(tick, 50);
  };
  tick();
})"""


async def hover(ctx: ActionContext, ref: str) -> str:
    """Move the mouse over the element `ref` (opens hover menus and tooltips). Never asks.

    Raises:
        ActionError: If the tab is in Duo, the origin or frame is blocked, or the ref is stale.
    """
    target = await prepare_ref(ctx, ref)
    log = log_target("hover", ref, target.label)
    action = GatedAction(f"hover over {target.label}", log, target.frame_origin)
    check = gate_check(ctx, [target.label], target.frame_origin)
    await confirm_or_log(ctx, target.page, action, log_only(check))
    result = f"hovering over {wrap_untrusted(target.label)}"
    if not await act_checked(ctx, target.page, None, target.locator.hover, [target.label]):
        return f"{result}; {DIALOG_OPENED_NOTE}"
    return result


async def scroll(
    ctx: ActionContext, ref: str | None = None, direction: str = "down", amount: float = 1.0
) -> str:
    """Scroll the page, or the box holding `ref`, by `amount` screens. Never asks.

    Raises:
        ActionError: For a bad direction or amount, or the checks hover makes.
    """
    if direction not in DIRECTIONS:
        raise ActionError("bad direction: use up, down, left or right")
    if not 0 < amount <= MAX_SCREENS:
        raise ActionError(f"bad amount: use a number of screens above 0, up to {MAX_SCREENS:g}")
    dx, dy = DIRECTIONS[direction]
    if ref is None:
        page = await prepare_page(ctx)
        element: Locator = page.locator("html")
    else:
        target = await prepare_ref(ctx, ref)
        page, element = target.page, target.locator
        log = log_target("scroll", ref, target.label)
        action = GatedAction(f"scroll {target.label}", log, target.frame_origin)
        await confirm_or_log(ctx, page, action, log_only(gate_check(ctx, [], target.frame_origin)))
    box = await element.evaluate_handle(SCROLLER_JS, dy != 0)
    described: list[str] = []

    async def act() -> None:
        try:
            position, size, view = await box.evaluate(SCROLL_JS, [dx, dy, amount])
            grew_from = None
            if dx + dy > 0 and position + view >= size - 1:  # reached the end: more may load
                new_size = await box.evaluate(GROW_WAIT_JS, [dy != 0, size, GROW_WAIT_MS])
                if new_size > size:
                    grew_from, size = size, new_size
        finally:
            await box.dispose()
        described.append(_describe_scroll(direction, position, size, view, grew_from))

    if not await act_checked(ctx, page, None, act):
        return f"scrolled {direction}; {DIALOG_OPENED_NOTE}"
    return described[0]


def _describe_scroll(
    direction: str, position: float, size: float, view: float, grew_from: float | None
) -> str:
    """E.g. "scrolled down: showing 720-1440 of 3000 px; it grew from 2000 px"."""
    start, end = round(position), round(position + view)
    text = f"scrolled {direction}: showing {start}-{end} of {round(size)} px"
    if grew_from is not None:
        return f"{text}; it grew from {round(grew_from)} px (more content loaded)"
    if end >= round(size) - 1 or start <= 0:
        return f"{text}; at the {'end' if end >= round(size) - 1 else 'start'}"
    return text
