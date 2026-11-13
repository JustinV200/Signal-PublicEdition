"""Ask the owner about a sensitive action, or log it when it is auto-allowed.

The gate rules (confirmation.py) return a GateCheck. One that must be confirmed
goes to the owner's dialog through ctx.confirmer; any other runs and gets one
INFO log line: the tool, the ref or key, the page origin and why it would have
asked. Log lines never hold page text or typed text, because a ref label can
carry a secret that leaked into an element's name, which only the result scrub
(server.ToolRunner) removes.
"""

import logging
from typing import NamedTuple

from playwright.async_api import Page

from browser_tool.actions.context import ActionContext
from browser_tool.actions.errors import ActionError
from browser_tool.actions.untrusted import wrap_untrusted
from browser_tool.gates import ConfirmationRequest, GateCheck
from browser_tool.policy import origin_of

logger = logging.getLogger(__name__)


GATE_CHANGED = (
    "refused: the element changed after it was checked and now needs the owner's "
    "approval ({reason}), so it was not clicked. Take a new snapshot and try again"
)


def ensure_not_stricter(checked: GateCheck | None, now: GateCheck | None) -> None:
    """Refuse when a re-check right before the click asks more than the first check did.

    The owner approved (or nobody was asked about) what the first check saw; a
    page that changed the element meanwhile gets no click on that approval.

    Raises:
        ActionError: If `now` asks and `checked` didn't, asked for another
            reason, or asked for fewer categories ("Send" that became "Send and
            delete").
    """
    if now is None or not now.must_confirm:
        return
    if (
        checked is not None
        and checked.must_confirm
        and checked.reason == now.reason
        and now.asking <= checked.asking
    ):
        return
    raise ActionError(GATE_CHANGED.format(reason=now.reason))


class GatedAction(NamedTuple):
    """An action a gate rule may hold for the owner.

    Attributes:
        prompt: What the dialog shows, e.g. 'click button "Buy now"' (page-supplied text).
        log_target: The same without page text, for logs, e.g. "click e12 (button)".
        frame_origin: The element's frame origin when it is a mismatch, else None.
    """

    prompt: str
    log_target: str
    frame_origin: str | None


async def confirm_or_log(
    ctx: ActionContext, page: Page, action: GatedAction, check: GateCheck | None
) -> str | None:
    """Ask the owner if `check` must be confirmed; otherwise log it and go on.

    Args:
        ctx: The action context (its confirmer is used).
        page: The page the action targets (its live origin goes in the dialog).
        action: What is about to happen.
        check: The gate rules' verdict, or None when no rule applies.

    Returns:
        The page origin the owner approved, or None when nobody was asked. Pass
        it to guards.ensure_ready_to_act: the tab may have moved while the owner
        decided.

    Raises:
        ActionError: If the owner declines, doesn't answer, or the dialog fails.
    """
    if check is None:
        return None
    if not check.must_confirm:
        logger.info(
            "auto-allowed %s on %s: %s", action.log_target, origin_of(page.url), check.reason
        )
        return None
    return await _ask_owner(ctx, page, action, check.reason)


async def _ask_owner(ctx: ActionContext, page: Page, action: GatedAction, reason: str) -> str:
    """Show the owner's dialog; return the origin it showed if they approve."""
    # The origin comes from the browser's own record of the page URL, not page text.
    origin = origin_of(page.url)
    request = ConfirmationRequest(
        action=action.prompt,
        origin=origin,
        reason=reason,
        frame_origin=action.frame_origin,
        job=ctx.session.job_label,
    )
    try:
        is_approved = await ctx.confirmer.confirm(request)
    except Exception as error:  # noqa: BLE001 - a broken dialog must mean "no"
        logger.error("confirmation dialog failed (%s); treating as declined", type(error).__name__)
        is_approved = False
    if not is_approved:
        raise ActionError(
            f"not done: the owner did not approve {wrap_untrusted(action.prompt)} ({reason})"
        )
    return origin
