"""The last moment before a page action: re-check it, run it, say where the tab landed.

recheck_refs judges ref targets again right before the action (click, drag)
and refuses one that now asks more than was approved
(gating.ensure_not_stricter). act_and_report is shared by click, click_at,
drag and press_key. act_and_report runs the action
inside a navigation.NavigationWatch, with guards.ensure_ready_to_act right
before it and no await in between, then lets the watch settle: if the action
started a main-frame navigation, it waits for it to land; otherwise it returns
at once. It then names the URL (query and fragment dropped,
path decoded and scrubbed, see secret_scrub.shown_url), a tab the action
closed or opened, blocked navigations, and the signed-out note on a login page.

A page dialog freezes the tab, and Playwright's click or press then never
returns. So the action and the settle run through session.act_until_dialog and
read_until_dialog: when the action opens a confirm, prompt or beforeunload,
act_and_report stops waiting, leaves the action to finish once the dialog is
answered, and reports it (the tool runner adds the dialog's text to every
result while it is open). The action's texts (`trigger`) are kept with the tab,
so answer_dialog gates on them too.
"""

from collections.abc import Awaitable, Callable, Sequence

from playwright.async_api import Page

from browser_tool.actions.context import ActionContext
from browser_tool.actions.errors import ActionError
from browser_tool.actions.gating import click_gate_check, ensure_not_stricter
from browser_tool.actions.guards import drain_block_note, ensure_ready_to_act
from browser_tool.actions.navigation import NavigationWatch, settle_max_s
from browser_tool.actions.pointer.target import RefTarget
from browser_tool.actions.secret_scrub import shown_url
from browser_tool.actions.signin import signed_out_note
from browser_tool.gates import GateCheck, strictest
from browser_tool.session import act_until_dialog, read_until_dialog

TAB_CLOSED_NOTE = "the tab closed; use tabs() and switch_tab()"
REF_GONE = "refused: the element is not on the page any more; take a new snapshot"
DIALOG_OPENED_NOTE = "it opened a dialog, which waits for answer_dialog (below)"


async def recheck_refs(
    ctx: ActionContext,
    targets: Sequence[RefTarget],
    approved_origin: str | None,
    check: GateCheck | None,
) -> None:
    """Judge the targets again right before the action; refuse if it now asks more.

    The tab checks come first, so a tab that moved (to Duo, or off the approved
    origin) is refused at once instead of waiting on a stale ref. No scroll:
    the targets were judged in place already.

    Args:
        ctx: The action context.
        targets: The ref targets the action touches (both ends of a drag).
        approved_origin: The origin the owner approved, or None.
        check: What the first check found (the strictest over the targets).

    Raises:
        ActionError: If the tab moved, a ref is gone, or the action now asks more.
    """
    page = targets[0].page
    ensure_ready_to_act(ctx, page, approved_origin)
    for target in targets:
        if await target.locator.count() != 1:
            raise ActionError(REF_GONE)
    now = [
        await click_gate_check(
            ctx, target.locator, target.label, target.frame_origin, scroll_first=False
        )
        for target in targets
    ]
    ensure_not_stricter(check, strictest(*now))


async def act_and_report(
    ctx: ActionContext,
    page: Page,
    approved_origin: str | None,
    act: Callable[[], Awaitable[object]],
    done: str,
    *,
    start_grace_s: float = 0.0,
    trigger: Sequence[str] = (),
) -> str:
    """Check the tab one last time, run `act`, let it settle and report.

    Args:
        ctx: The action context.
        page: The tab acted on.
        approved_origin: The origin the owner approved, or None (confirm_or_log's result).
        act: The page action, e.g. lambda: locator.click().
        done: What was done, for the result, e.g. 'clicked <label>'.
        start_grace_s: How long a navigation gets to start (press_key: a key
            press returns before the navigation it set off starts).
        trigger: The action's texts (e.g. the clicked label), which a dialog it
            opens is gated on too (DialogWatch.note_trigger).

    Raises:
        ActionError: If ensure_ready_to_act refuses (Duo, origin, or the tab moved
            off the approved origin); nothing was done then.
    """
    tabs_before = len(ctx.session.pages())
    ctx.session.block_log.drain()
    dialogs = ctx.session.dialogs
    # Marked as acting throughout, so the tool runner leaves a dialog opened
    # here (or while settling) to this function.
    dialogs.begin_act(page)
    try:
        with NavigationWatch(page) as watch:
            if await act_checked(ctx, page, approved_origin, act, trigger):
                await read_until_dialog(
                    dialogs, page, lambda: watch.settle(settle_max_s(ctx), start_grace_s)
                )
    finally:
        dialogs.end_act(page)
    return await _report_after_action(ctx, page, done, tabs_before)


async def act_checked(
    ctx: ActionContext,
    page: Page,
    approved_origin: str | None,
    act: Callable[[], Awaitable[object]],
    trigger: Sequence[str] = (),
) -> bool:
    """ensure_ready_to_act, then `act`, in one task; stop waiting if it opens a dialog.

    Args:
        ctx: The action context.
        page: The tab acted on.
        approved_origin: The origin the owner approved, or None.
        act: The page action.
        trigger: The action's texts, kept for a dialog it opens (note_trigger).

    Returns:
        True when `act` finished, False when it opened a dialog first (it then
        runs on, and finishes once the dialog is answered).

    Raises:
        ActionError: If ensure_ready_to_act refuses; nothing was done then.
    """
    ctx.session.dialogs.note_trigger(page, tuple(trigger))

    async def checked_act() -> None:
        # The owner's dialog may have taken a while: the tab can be in Duo or
        # elsewhere. Checked in the action's own task, with no await before the act.
        ensure_ready_to_act(ctx, page, approved_origin)
        await act()

    return await act_until_dialog(ctx.session.dialogs, page, checked_act)


async def _report_after_action(ctx: ActionContext, page: Page, done: str, tabs_before: int) -> str:
    """Report the (settled) tab's URL, new tabs, blocked navigations and the signed-out note.

    A tab the action closed (an OAuth popup's window.close()) is still a success:
    the action ran, and reporting a failure would invite a repeat.

    Args:
        ctx: The action context.
        page: The tab acted on.
        done: What was done, e.g. 'clicked <label>'.
        tabs_before: How many tabs were open before the action.
    """
    if page.is_closed():
        parts = [done, TAB_CLOSED_NOTE]
    else:
        shown = await shown_url(ctx, page.url)
        parts = [done, f"now at {shown}", await signed_out_note(ctx, page)]
        if ctx.session.dialogs.pending(page) is not None:
            parts.append(DIALOG_OPENED_NOTE)
    tabs_now = len(ctx.session.pages())
    if tabs_now > tabs_before:
        parts.append(f"a new tab opened (tab {tabs_now - 1}); use tabs() and switch_tab()")
    parts.append(drain_block_note(ctx))
    return "; ".join(part for part in parts if part)
