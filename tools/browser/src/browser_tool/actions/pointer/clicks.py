"""The click tool: click a snapshot ref, with a mouse button, a double click and modifier keys.

Every variant goes through the same gate path as a plain click: the Duo lockout
and origin check first (target.prepare_ref), the click rules on the element
and everything a click on it can reach (gating.click_gate_check: purchase,
send and delete text, form submits, frames), the owner's dialog when the rule
asks, and the last-moment check right before the click (after_action.act_and_report).
The mouse hovers the element first and hover effects get a moment to settle
(target.hover_settle_gate), so a hover that swaps in "Send" is judged as Send.
Right before the click the rules run again, and a click that now asks more
than was approved is refused (after_action.recheck_refs). A double click is
two halves with that re-check between them: its first click can swap in new
content ("Edit" turning into "Send"), which the second half would otherwise
press. The first click goes to the centre of the element's box; before the
second the mouse returns there, and the element hit at that point (through
shadow roots and iframes, click_at.element_at) must be the ref's element or
inside it, so a first click that scrolled or moved the page can't make the
second land on another button. A first click that opened a dialog gets no
second half: it would run only once the dialog is answered. A page that
changes the element on pointerdown, or in the last tens of ms, isn't caught,
and a page can always send from an innocent label's onclick (README, Known
gaps). A right, middle or
modified click is gated as strictly as a left one: a Control+click still
fires the element's handlers.
"""

from collections.abc import Sequence
from typing import NamedTuple

from playwright.async_api import Error as PlaywrightError
from playwright.async_api import Page, Position

from browser_tool.actions.context import ActionContext
from browser_tool.actions.errors import ActionError
from browser_tool.actions.gating import GatedAction, click_gate_check, confirm_or_log
from browser_tool.actions.guards import ensure_ready_to_act
from browser_tool.actions.pointer.after_action import REF_GONE, act_and_report, recheck_refs
from browser_tool.actions.pointer.click_at import element_at
from browser_tool.actions.pointer.target import (
    RefTarget,
    hover_settle_gate,
    log_target,
    prepare_ref,
)
from browser_tool.actions.untrusted import wrap_untrusted
from browser_tool.gates import GateCheck

BUTTONS = ("left", "right", "middle")
MODIFIERS = ("Alt", "Control", "Meta", "Shift")
SECOND_HALF_REFUSED = "the first click of the double click ran, but the second was refused: {why}"
PAGE_MOVED = "the page moved, so another element is under the click point now"
DIALOG_BETWEEN = "the first click opened a dialog"
# The hit element is the ref's element or inside it, across shadow roots.
CONTAINS_JS = """(el, hit) => {
  for (let n = hit; n; n = n.parentNode || n.host) if (n === el) return true;
  return false;
}"""


class ClickOptions:
    """How to click: the button, double or not, and the modifier keys held.

    Attributes:
        button: "left", "right" or "middle".
        double: Double-click.
        modifiers: Keys held during the click (Alt, Control, Meta, Shift), deduplicated.
    """

    def __init__(self, button: str, double: bool, modifiers: Sequence[str]) -> None:
        """Validate the options.

        Raises:
            ActionError: If the button or a modifier isn't one Playwright knows.
        """
        if button not in BUTTONS:
            raise ActionError(f"bad button {button!r}: use left, right or middle")
        unknown = [key for key in modifiers if key not in MODIFIERS]
        if unknown:
            raise ActionError(f"bad modifier {unknown[0]!r}: use Alt, Control, Meta or Shift")
        self.button = button
        self.double = double
        self.modifiers = list(dict.fromkeys(modifiers))

    @property
    def name(self) -> str:
        """For dialogs, logs and results, e.g. "click" or "Control+double-click"."""
        kind = "double-" if self.double else ""
        kind += "" if self.button == "left" else f"{self.button}-"
        return "+".join([*self.modifiers, kind + "click"])


async def click(
    ctx: ActionContext,
    ref: str,
    button: str = "left",
    double: bool = False,
    modifiers: Sequence[str] = (),
) -> str:
    """Click the element `ref` from the latest snapshot, asking the owner if sensitive.

    Args:
        ctx: The action context.
        ref: The element's snapshot ref.
        button: "left", "right" or "middle".
        double: Double-click.
        modifiers: Keys held during the click: any of Alt, Control, Meta, Shift.

    Raises:
        ActionError: For a bad button or modifier, a refused or declined click.
    """
    options = ClickOptions(button, double, modifiers)
    target = await prepare_ref(ctx, ref)

    async def gate() -> GateCheck | None:
        return await click_gate_check(ctx, target.locator, target.label, target.frame_origin)

    check = await hover_settle_gate(target.page, target.locator.hover, gate)
    how = options.name
    log = log_target(how, ref, target.label)
    action = GatedAction(f"{how} {target.label}", log, target.frame_origin)
    approved_origin = await confirm_or_log(ctx, target.page, action, check)
    await recheck_refs(ctx, [target], approved_origin, check)
    # A double click needs its point: both halves go there (None: Playwright's default).
    point = await _centre(target) if options.double else None
    dialogs_before = ctx.session.dialogs.opened_count(target.page)

    async def act() -> None:
        await target.locator.click(
            button=options.button,  # type: ignore[arg-type]  # checked by ClickOptions
            modifiers=options.modifiers,  # type: ignore[arg-type]
            position=point.offset if point else None,
        )
        if point:
            # A dialog the first click opened was answered by then: the second
            # click would land on whatever the answer left.
            if ctx.session.dialogs.opened_count(target.page) != dialogs_before:
                raise ActionError(SECOND_HALF_REFUSED.format(why=DIALOG_BETWEEN))
            second = _SecondHalf(target, approved_origin, check, options, point)
            await second.run(ctx)

    return await act_and_report(
        ctx,
        target.page,
        approved_origin,
        act,
        f"{how}ed {wrap_untrusted(target.label)}",
        trigger=[target.label],
    )


class ClickPoint(NamedTuple):
    """Where a double click lands.

    Attributes:
        x: Viewport x in CSS pixels.
        y: Viewport y in CSS pixels.
        offset: The same point inside the element's box, for locator.click(position=).
    """

    x: float
    y: float
    offset: Position


async def _centre(target: RefTarget) -> ClickPoint:
    """The centre of the element's box, in the viewport and inside the box.

    Raises:
        ActionError: If the element has no box (gone or not rendered).
    """
    box = await target.locator.bounding_box()
    if box is None:
        raise ActionError(REF_GONE)
    half_width, half_height = box["width"] / 2, box["height"] / 2
    offset: Position = {"x": half_width, "y": half_height}
    return ClickPoint(box["x"] + half_width, box["y"] + half_height, offset)


class _SecondHalf(NamedTuple):
    """The second click of a double click, and what it was approved for."""

    target: RefTarget
    approved_origin: str | None
    check: GateCheck | None
    options: ClickOptions
    point: ClickPoint

    async def run(self, ctx: ActionContext) -> None:
        """Re-check after the first click, hit-test the point, then press again there.

        click_count=2 makes the browser treat it as the second click (dblclick fires).

        Raises:
            ActionError: SECOND_HALF_REFUSED when the re-check or the hit test refuses.
        """
        page = self.target.page
        try:
            await recheck_refs(ctx, [self.target], self.approved_origin, self.check)
            await page.mouse.move(self.point.x, self.point.y)
            await _ensure_hit(ctx, self.target, self.point)
            ensure_ready_to_act(ctx, page, self.approved_origin)
        except ActionError as error:
            raise ActionError(SECOND_HALF_REFUSED.format(why=error)) from None
        await _press_again(page, self.options)


async def _ensure_hit(ctx: ActionContext, target: RefTarget, point: ClickPoint) -> None:
    """Refuse unless the element at the point is the ref's element or inside it.

    Raises:
        ActionError: PAGE_MOVED if another element (or one in another frame) is there.
    """
    hit, _ = await element_at(ctx, target.page, point.x, point.y)
    element = await target.locator.element_handle()
    try:
        is_inside = await element.evaluate(CONTAINS_JS, hit)
    except PlaywrightError:  # a handle from another frame: not inside
        is_inside = False
    finally:
        await hit.dispose()
        await element.dispose()
    if not is_inside:
        raise ActionError(PAGE_MOVED)


async def _press_again(page: Page, options: ClickOptions) -> None:
    """The second click of a double click: mouse down and up, holding the modifiers.

    Only what was actually pressed is released: the keys that went down, and
    the button once its down succeeded, even when a later step fails.
    """
    button = options.button
    pressed: list[str] = []
    try:
        for key in options.modifiers:
            await page.keyboard.down(key)
            pressed.append(key)
        await page.mouse.down(button=button, click_count=2)  # type: ignore[arg-type]
        # Nothing runs between down and up, so up follows exactly a successful down.
        await page.mouse.up(button=button, click_count=2)  # type: ignore[arg-type]
    finally:
        for key in reversed(pressed):
            await page.keyboard.up(key)
