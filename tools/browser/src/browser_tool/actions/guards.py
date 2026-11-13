"""Checks run before actions: Duo lockout, dialogs, origin, filled credentials, refs, frames.

Duo rule (see browser_tool.duo): no acting tool touches a tab that shows a Duo
two-factor prompt. Origin rules (see browser_tool.policy): the page must be on an
allowed http(s) origin. An element inside an about:blank/srcdoc/data:/blob: frame is an origin
mismatch: the caller's gate rules log acting on it (gating.confirmation). An
element inside a frame from a blocked host is refused outright. Dialog rule (see
browser_tool.session.dialogs): a tab with a confirm, prompt or beforeunload open
is frozen until it is answered, so ensure_page_allowed (which every action and
read tool runs) refuses it, pointing at answer_dialog. ensure_ready_to_act
repeats the Duo, dialog and origin checks right before an element or key
action, and holds an approved action to the origin the owner approved.
"""

import logging
import re

from playwright.async_api import Frame, Locator, Page

from browser_tool.actions.context import ActionContext
from browser_tool.actions.errors import ActionError
from browser_tool.duo import DUO_LOCKOUT_MESSAGE
from browser_tool.policy import REASON_OPAQUE_ORIGIN, origin_of

logger = logging.getLogger(__name__)

REF_PATTERN = re.compile(r"^(f\d+)?e\d+$")
FILLED_CREDENTIALS_MESSAGE = "blocked: credentials filled on this page; navigate or submit first"
CREDENTIAL_CHECK_FAILED = "blocked: could not check this page for filled credentials"
# How ensure_ready_to_act's refusal starts when the tab left the approved origin.
TAB_MOVED_REFUSAL = "refused: the tab moved from"
DIALOG_OPEN_REFUSAL = (
    "refused: a {kind} dialog is open on this tab and the page is frozen until it is "
    "answered; use answer_dialog(accept=true or false) first"
)


def ensure_page_allowed(ctx: ActionContext, page: Page) -> None:
    """Refuse a page with an open dialog, or whose origin the policy doesn't allow.

    Raises:
        ActionError: If a dialog is open on the page (ensure_no_dialog), or it
            is on a blocked, opaque or non-web origin.
    """
    ensure_no_dialog(ctx, page)
    decision = ctx.policy.check_url(page.url)
    if not decision.is_allowed:
        raise ActionError(
            f"blocked: the current page ({origin_of(page.url)}) is not on an allowed origin "
            f"({decision.reason}); navigate to an allowed site first"
        )


def ensure_no_dialog(ctx: ActionContext, page: Page) -> None:
    """Refuse a tab with a confirm, prompt or beforeunload open (answer_dialog answers it).

    Raises:
        ActionError: DIALOG_OPEN_REFUSAL.
    """
    pending = ctx.session.dialogs.pending(page)
    if pending is not None:
        raise ActionError(DIALOG_OPEN_REFUSAL.format(kind=pending.kind))


def ensure_not_in_duo(ctx: ActionContext, page: Page) -> None:
    """Refuse to act on a tab showing a Duo prompt: only the owner answers Duo.

    Every tool that changes page state calls this first (reload too: reloading
    a Duo prompt sends a new push). The pointer tools (click, click_at, drag,
    hover, scroll), type_text, select_option and press_key call it again right
    before they touch the page (through ensure_ready_to_act), since an owner
    dialog can wait long enough for the tab to redirect to Duo. fill_login
    doesn't: the vault re-checks the page's origin itself right before it fills.
    navigate, back, forward, switch_tab, new_tab and close_tab never call it, so
    the model can still leave; the one exception is the retry of an approved
    form resubmission by back or forward, which runs ensure_ready_to_act.

    Raises:
        ActionError: If the tab is in Duo (see browser_tool.duo.DuoWatch.is_in_duo).
    """
    if ctx.session.duo.is_in_duo(page):
        raise ActionError(DUO_LOCKOUT_MESSAGE)


def ensure_ready_to_act(ctx: ActionContext, page: Page, approved_origin: str | None) -> None:
    """The last check before a click, fill, select or key press; no await may come in between.

    An owner dialog can wait up to [gates] confirm_timeout_s, and the tab can move
    on meanwhile. press_key has no element to pin it to a page, so without this an
    approved "press Enter on site A" would press Enter on whatever the tab shows by
    then.

    Args:
        ctx: The action context.
        page: The tab about to be acted on.
        approved_origin: The origin the owner approved (owner_prompt.confirm_or_log's
            return value), or None for an action that needed no approval.

    Raises:
        ActionError: If the tab is in Duo, has a dialog open, is on an origin the
            policy doesn't allow, or is no longer on the origin the owner approved.
    """
    ensure_not_in_duo(ctx, page)
    ensure_page_allowed(ctx, page)
    current_origin = origin_of(page.url)
    if approved_origin is not None and current_origin != approved_origin:
        raise ActionError(
            f"{TAB_MOVED_REFUSAL} {approved_origin} to {current_origin} while the "
            "owner was deciding, so their approval no longer applies and nothing was done. "
            "Take a new snapshot and try again."
        )


async def ensure_no_filled_credentials(ctx: ActionContext, page: Page) -> None:
    """Refuse while the vault reports filled fields on `page`. Fails closed.

    Raises:
        ActionError: If fields are filled, or the check itself fails.
    """
    try:
        has_filled = await ctx.filler.has_filled_fields(page)
    except Exception as error:  # noqa: BLE001 - any failure must block (fail closed)
        logger.warning("has_filled_fields failed (%s); blocking", type(error).__name__)
        raise ActionError(CREDENTIAL_CHECK_FAILED) from None
    if has_filled:
        raise ActionError(FILLED_CREDENTIALS_MESSAGE)


def ensure_ref_format(ref: str) -> None:
    """Refuse a ref that isn't shaped like a snapshot ref (e12, or f1e3 inside a frame).

    Raises:
        ActionError: If the ref is malformed.
    """
    if not REF_PATTERN.match(ref):
        raise ActionError(f"bad ref {ref!r}: use a ref like e12 or f1e3 from snapshot()")


async def resolve_ref(page: Page, ref: str) -> Locator:
    """Turn a snapshot ref into a locator for exactly one element.

    Raises:
        ActionError: If the ref is malformed or doesn't match exactly one element.
    """
    ensure_ref_format(ref)
    target = page.get_by_ref(ref)
    if await target.count() != 1:
        raise ActionError(f"ref {ref} is not on the page any more; take a new snapshot")
    return target


async def frame_mismatch_origin(ctx: ActionContext, page: Page, target: Locator) -> str | None:
    """Check the frame that holds `target` (see frame_check).

    Raises:
        ActionError: If the frame belongs to a blocked host or a non-web scheme.
    """
    handle = await target.element_handle()
    try:
        frame = await handle.owner_frame()
    finally:
        await handle.dispose()
    return frame_check(ctx, page, frame)


def frame_check(ctx: ActionContext, page: Page, frame: Frame | None) -> str | None:
    """Check one frame of `page` against the policy.

    Returns:
        None for the main frame or an allowed frame; the frame's display origin
        when it has an opaque origin (the gate rules log acting in it).

    Raises:
        ActionError: If the frame belongs to a blocked host or a non-web scheme.
    """
    if frame is None or frame == page.main_frame:
        return None
    decision = ctx.policy.check_url(frame.url)
    if decision.is_allowed:
        return None
    if decision.reason == REASON_OPAQUE_ORIGIN:
        return origin_of(frame.url)
    raise ActionError(
        f"blocked: the element is in a frame from {origin_of(frame.url)} ({decision.reason})"
    )


def drain_block_note(ctx: ActionContext) -> str:
    """Describe navigations blocked since the last drain, or "" if none.

    Subresource blocks are counted but not listed, to keep results short.
    """
    blocked = ctx.session.block_log.drain()
    navigations = sorted({entry.origin for entry in blocked if entry.is_navigation})
    others = sum(1 for entry in blocked if not entry.is_navigation)
    notes = []
    if navigations:
        notes.append(f"blocked navigation to non-allowed origin(s): {', '.join(navigations)}")
    if others:
        notes.append(f"blocked {others} request(s) to non-allowed hosts")
    return "; ".join(notes)
