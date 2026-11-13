"""wait_for_duo: wait, read only, for the owner to approve a Duo prompt, then carry on.

It never acts in Duo: no click, key, fill or script reaches the page. It reads
whether the tab is in Duo (DuoWatch.is_in_duo) and the voice heads-up's outcome,
and waits with duo.wait_until_off_duo. Duo heads-ups ring through sleep and
away, so a current hub speaks them, but the owner may still not answer: then
the wait ends in the clean timeout text. When a hub that doesn't honour
ring-through dropped the heads-up, it returns at once unless wait_anyway, since
nobody heard it. Once the tab leaves Duo, it waits for the landing to settle (load, then
about 1 s with no main-frame navigation, duo.wait_for_settle), so a hand-off
page on the way back isn't taken for the landing. Then navigate's landing backstop runs
(landing.report_location), so a blocked landing is cleared and a login page
gets its signed-out note.
"""

from signal_hub_notify import Delivery, DeliveryStatus

from browser_tool.actions.context import ActionContext
from browser_tool.actions.errors import ActionError
from browser_tool.actions.signin.landing import report_location
from browser_tool.duo import (
    PingOutcome,
    WaitOutcome,
    ping_line,
    wait_for_settle,
    wait_until_off_duo,
)

DEFAULT_WAIT_S = 90.0
MAX_WAIT_S = 300.0
NOT_IN_DUO = "no Duo prompt on this tab"
TAB_CLOSED = "the tab closed; use tabs() and switch_tab()"
STILL_ON_PHONE = "the push is still on the phone; call wait_for_duo again later or move on"
TIMED_OUT = (
    "the Duo prompt is still waiting after {wait_s:g} s ({line}); call wait_for_duo "
    "again or move on"
)
APPROVED_VERB = "Duo approved; now at"
BAD_TIMEOUT = "bad timeout_s: use a number of seconds above 0 (at most 300)"


async def wait_for_duo(
    ctx: ActionContext, timeout_s: float = DEFAULT_WAIT_S, wait_anyway: bool = False
) -> str:
    """Wait for the current tab to leave its Duo prompt, for up to timeout_s (at most 300).

    Args:
        ctx: The action context.
        timeout_s: Seconds to wait, capped at MAX_WAIT_S.
        wait_anyway: Wait even when the voice heads-up was dropped.

    Returns:
        "Duo approved; now at <url>" (plus any signed-out note), the timeout text
        with the voice ping line, the dropped-ping text, NOT_IN_DUO or TAB_CLOSED.

    Raises:
        ActionError: On a timeout_s that isn't above 0, or a landing the policy
            blocks (the tab is cleared).
    """
    if not timeout_s > 0:  # also catches NaN
        raise ActionError(BAD_TIMEOUT)
    wait_s = min(timeout_s, MAX_WAIT_S)
    page = await ctx.session.current_page()
    duo = ctx.session.duo
    if not duo.is_in_duo(page):
        return NOT_IN_DUO
    outcome = await duo.ping_outcome(page)
    line = ping_line(outcome, ctx.settings.duo.min_heads_up_interval_s)
    if _is_dropped(outcome) and not wait_anyway:
        return f"{line}; {STILL_ON_PHONE}"
    ended = await wait_until_off_duo(page, wait_s, duo.is_in_duo)
    if ended is WaitOutcome.CLOSED:
        return TAB_CLOSED
    if ended is WaitOutcome.TIMEOUT:
        return TIMED_OUT.format(wait_s=wait_s, line=line)
    await wait_for_settle(page)
    if page.is_closed():
        return TAB_CLOSED
    return await report_location(ctx, page, APPROVED_VERB)


def _is_dropped(outcome: PingOutcome | None) -> bool:
    """True when the hub dropped the heads-up unspoken (a hub without ring-through)."""
    return isinstance(outcome, Delivery) and outcome.status is DeliveryStatus.DROPPED
