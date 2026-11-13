"""Run browser work that a page dialog can freeze, without hanging on it.

While a confirm, prompt or beforeunload is open, Playwright's click, press,
fill and evaluate on that tab don't return (measured on headless Edge, and per
Playwright's docs). Each helper here runs its work as a task and stops waiting
when a dialog opens:
- act_until_dialog: an action (a click) whose dialog is the expected answer to
  it. The action is left running (it finishes once the dialog is answered)
  and the caller reports the dialog. The dialog is marked during_act.
- read_until_dialog: read-only work (a scrub's field read, a settle). It is
  cancelled, and the caller falls back.
- run_unless_dialog: a whole tool call (the tool runner). A dialog on the
  current tab that did not open during an act means the tool got stuck
  before it acted, e.g. in a gate check after a hover: the call is cancelled
  and refused.
"""

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

from playwright.async_api import Page

from browser_tool.errors import ActionError
from browser_tool.session.dialogs.watch import DialogWatch, PendingDialog

STOPPED_BY_DIALOG = (
    "stopped: the page opened a {kind} dialog while {tool} ran, so it may not have "
    "finished. Answer the dialog with answer_dialog(accept=true or false), then take "
    "a new snapshot"
)


async def _first_of(
    watch: DialogWatch, task: asyncio.Future[Any], wanted: Callable[[PendingDialog], bool]
) -> PendingDialog | None:
    """Wait for `task`, or for a dialog `wanted` accepts; that dialog, or None if `task` ended.

    `task` is cancelled if this wait itself is cancelled.
    """
    opened: asyncio.Future[PendingDialog] = asyncio.get_running_loop().create_future()

    def on_open(pending: PendingDialog) -> None:
        if wanted(pending) and not opened.done():
            opened.set_result(pending)

    unsubscribe = watch.subscribe(on_open)
    try:
        await asyncio.wait({task, opened}, return_when=asyncio.FIRST_COMPLETED)
    except BaseException:
        task.cancel()
        raise
    finally:
        unsubscribe()
    # Both done at once: the work finished, so report it as finished.
    return None if task.done() else opened.result()


async def act_until_dialog(
    watch: DialogWatch, page: Page, act: Callable[[], Awaitable[object]]
) -> bool:
    """Run `act` on `page`; stop waiting if it opens a dialog there.

    Returns:
        True when `act` finished (its errors are raised), False when a dialog
        opened first; `act` then runs on in the background.
    """
    watch.begin_act(page)
    try:
        task = asyncio.ensure_future(act())
        opened = await _first_of(watch, task, lambda pending: pending.page is page)
    finally:
        watch.end_act(page)
    if opened is None:
        task.result()
        return True
    watch.keep(task)
    return False


async def read_until_dialog[Result](
    watch: DialogWatch, page: Page, read: Callable[[], Awaitable[Result]]
) -> tuple[bool, Result | None]:
    """Run read-only `read` on `page`, unless a dialog is or becomes open there.

    Returns:
        (True, its result), or (False, None) when a dialog is open (it is cancelled).
    """
    if watch.pending(page) is not None:
        return False, None
    watch.begin_act(page)  # the runner must not cancel the tool for this one
    try:
        task = asyncio.ensure_future(read())
        opened = await _first_of(watch, task, lambda pending: pending.page is page)
    finally:
        watch.end_act(page)
    if opened is None:
        return True, task.result()
    task.cancel()
    watch.keep(task)
    return False, None


async def run_unless_dialog[Result](
    watch: DialogWatch,
    work: Awaitable[Result],
    current: Callable[[], Page | None],
    tool: str,
) -> Result:
    """Run a tool call; refuse it if a dialog it didn't act for freezes the current tab.

    Args:
        watch: The session's dialog watch.
        work: The tool call.
        current: The current tab, checked when a dialog opens.
        tool: The tool's name, for the refusal.

    Raises:
        ActionError: STOPPED_BY_DIALOG; the call is cancelled and left to unwind
            in the background (awaiting it could hang on the frozen tab).
    """
    task = asyncio.ensure_future(work)

    def is_stuck(pending: PendingDialog) -> bool:
        return not pending.during_act and pending.page is current()

    opened = await _first_of(watch, task, is_stuck)
    if opened is None:
        return task.result()
    task.cancel()
    watch.keep(task)
    raise ActionError(STOPPED_BY_DIALOG.format(kind=opened.kind, tool=tool))
