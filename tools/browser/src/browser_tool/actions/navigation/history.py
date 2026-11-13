"""The history tools: back, forward and reload.

Each step runs inside a NavigationWatch (so the landing settles) and a
ResubmitGuard. Edge would silently send a form's POST again when a step lands
on a page a form submitted to, in the main frame or an iframe; the guard holds
that back, and the step then runs the send rule: with send in [gates]
always_confirm the owner is asked, and only on an Allow does the step run
again with the guard off (ensure_ready_to_act right before it). Otherwise it
is logged and runs again. A step that turned into a download, or was blocked
by the policy, is described like navigate's (load_failure). A step that
didn't move any frame (no navigation seen and the URL unchanged) is "no
previous page" or "no next page"; a hash-only step counts as a move.

A step through an iframe's history moves only that iframe, and Playwright's
go_back/go_forward would wait out the whole navigation timeout for a main-frame
navigation that never comes. So the wait ends early once only a child frame
moved (or a resubmission was held back), and a step that still times out after
any frame navigated counts as a move, not a failure.

Landings go through signin.report_location: the origin backstop, block notes
and the signed-out note. reload refuses a tab in Duo (reloading the prompt
sends a new push), checked right before every attempt. back and forward never
refuse Duo, so the model can always leave, except on the retry of an approved
form resubmission, which runs ensure_ready_to_act (Duo included) like any
other approved action. Every step refuses a tab with a dialog open (after
reload's Duo check): the page is frozen until answer_dialog answers it.
"""

import asyncio
from collections.abc import Awaitable, Callable
from contextlib import suppress
from typing import NamedTuple

from playwright.async_api import Error as PlaywrightError
from playwright.async_api import Page
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from browser_tool.actions.context import ActionContext
from browser_tool.actions.errors import ActionError
from browser_tool.actions.gating import GatedAction, confirm_or_log
from browser_tool.actions.guards import ensure_no_dialog, ensure_not_in_duo, ensure_ready_to_act
from browser_tool.actions.navigation.load_failure import describe_load_failure
from browser_tool.actions.navigation.nav_watch import NavigationWatch, settle_max_s
from browser_tool.actions.navigation.resubmit_guard import ResubmitGuard
from browser_tool.actions.secret_scrub import shown_url
from browser_tool.actions.signin import report_location
from browser_tool.config import CATEGORY_SEND

RESUBMIT_REASON = "it would send a form again (the page is a form's POST result)"
RESUBMIT_HELD_AGAIN = "refused: the form resubmission was held back; navigate to the page instead"
LOAD_STATE = "domcontentloaded"


class HistoryStep(NamedTuple):
    """One history tool.

    Attributes:
        name: What it does, for dialogs and download notes, e.g. "going back".
        verb: How its result starts, e.g. "went back to".
        nothing_there: The result when the tab didn't move, or None (a reload always moves).
        run: Runs the step on a tab.
        refuses_duo: Refuse a tab in Duo (reload: it would send a new push).
    """

    name: str
    verb: str
    nothing_there: str | None
    run: Callable[[Page], Awaitable[object]]
    refuses_duo: bool = False


BACK = HistoryStep(
    "going back",
    "went back to",
    "no previous page",
    lambda page: page.go_back(wait_until=LOAD_STATE),
)
FORWARD = HistoryStep(
    "going forward",
    "went forward to",
    "no next page",
    lambda page: page.go_forward(wait_until=LOAD_STATE),
)
RELOAD = HistoryStep(
    "reloading", "reloaded", None, lambda page: page.reload(wait_until=LOAD_STATE), True
)


async def back(ctx: ActionContext) -> str:
    """Go back one step in the current tab's history."""
    return await _take_step(ctx, await ctx.session.current_page(), BACK)


async def forward(ctx: ActionContext) -> str:
    """Go forward one step in the current tab's history."""
    return await _take_step(ctx, await ctx.session.current_page(), FORWARD)


async def reload(ctx: ActionContext) -> str:
    """Reload the current tab.

    Raises:
        ActionError: If the tab is in Duo, or the owner declined sending a form again.
    """
    return await _take_step(ctx, await ctx.session.current_page(), RELOAD)


async def _take_step(ctx: ActionContext, page: Page, step: HistoryStep) -> str:
    """Run `step` with resubmissions held back; on one, run the send rule and step again.

    Raises:
        ActionError: If the owner declined, a check refused (a Duo tab for
            reload, then an open dialog), or the load failed.
    """
    if step.refuses_duo:
        ensure_not_in_duo(ctx, page)
    ensure_no_dialog(ctx, page)
    result = await _run_step(ctx, page, step, holds_resubmit=True)
    if result is not None:
        return result
    action = GatedAction(f"{step.name}, sending a form again", f"{step.name} (resubmit)", None)
    check = ctx.rules.check(CATEGORY_SEND, RESUBMIT_REASON)
    approved_origin = await confirm_or_log(ctx, page, action, check)
    result = await _run_step(ctx, page, step, holds_resubmit=False, approved_origin=approved_origin)
    if result is None:  # the guard is off on the retry, so this shouldn't happen
        raise ActionError(RESUBMIT_HELD_AGAIN)
    return result


async def _run_step(
    ctx: ActionContext,
    page: Page,
    step: HistoryStep,
    *,
    holds_resubmit: bool,
    approved_origin: str | None = None,
) -> str | None:
    """Run `step` once and describe where the tab is.

    Args:
        ctx: The action context.
        page: The tab.
        step: The history step.
        holds_resubmit: Hold back a form resubmission (the first try). Off, the
            step is the approved (or logged) retry, checked by ensure_ready_to_act.
        approved_origin: On the retry, the origin the owner approved, if asked.

    Returns:
        The result text, or None when a resubmission was held back.
    """
    ctx.session.block_log.drain()
    before = page.url
    downloads_before = ctx.session.downloads.started
    with NavigationWatch(page) as watch:
        async with ResubmitGuard(page, is_active=holds_resubmit) as guard:
            try:
                # The last checks, with no await before the step starts.
                if not holds_resubmit:
                    ensure_ready_to_act(ctx, page, approved_origin)
                if step.refuses_duo:
                    ensure_not_in_duo(ctx, page)
                await _run_until_moved(page, step, watch, guard)
            except PlaywrightError as error:
                if guard.was_blocked:
                    return None
                # An iframe-only step can time out waiting for the main frame.
                is_move = isinstance(error, PlaywrightTimeoutError) and watch.has_any_navigated
                if not is_move:
                    return await describe_load_failure(
                        ctx, page, error, downloads_before, step.name
                    )
        # The guard is closed before the landing settles: a POST the landed page
        # sends itself (an auto-submitted login hand-off) is the page's, not a
        # resubmission, and must not be aborted unnoticed.
        if guard.was_blocked:
            return None
        if step.nothing_there and not watch.has_any_navigated and page.url == before:
            return f"{step.nothing_there}; still at {await shown_url(ctx, page.url)}"
        await watch.settle(settle_max_s(ctx))
    return await report_location(ctx, page, step.verb)


async def _run_until_moved(
    page: Page, step: HistoryStep, watch: NavigationWatch, guard: ResubmitGuard
) -> None:
    """Run the step, but stop waiting once only a child frame moved or a resubmission was held.

    The step's own errors propagate. When the wait ends early, the step's call
    is cancelled; its navigation has already happened (or was aborted).
    """
    # The step's task starts at the next loop turn, with no other await of ours first.
    step_task = asyncio.ensure_future(step.run(page))
    early = [
        asyncio.ensure_future(watch.wait_child_only_move()),
        asyncio.ensure_future(guard.blocked.wait()),
    ]
    is_early = False
    try:
        await asyncio.wait([step_task, *early], return_when=asyncio.FIRST_COMPLETED)
    finally:
        for task in early:
            task.cancel()
        # Ended early, or this call itself was cancelled: never leave the step running.
        if not step_task.done():
            is_early = True
            step_task.cancel()
            with suppress(asyncio.CancelledError, PlaywrightError):
                await step_task
    if not is_early:
        await step_task  # re-raises its error, if any
