"""report_location: backstop a landing, then say where the tab is now.

Shared by navigate, back, wait_for and wait_for_duo. Callers let the landing
settle first (navigate and back through navigation.NavigationWatch, which waits
only when a main-frame navigation actually happened; wait_for_duo through
duo.wait_for_settle), so a login hand-off has finished its redirects and the
signed-out note reads the page the tab ends on. A landing on an origin the policy
doesn't allow (e.g. behind a proxy, where DNS-level blocking doesn't apply)
clears the tab. Otherwise the result names the URL (query and fragment
dropped, path decoded and scrubbed, see secret_scrub.shown_url), any blocked
navigations, and the signed-out note when the main frame shows a visible
password field.
"""

from playwright.async_api import Page

from browser_tool.actions.context import ActionContext
from browser_tool.actions.errors import ActionError
from browser_tool.actions.guards import drain_block_note
from browser_tool.actions.secret_scrub import shown_url
from browser_tool.actions.signin.login_note import signed_out_note
from browser_tool.policy import origin_of

BLANK_PAGE = "about:blank"


async def report_location(ctx: ActionContext, page: Page, verb: str) -> str:
    """Backstop the (settled) landing's origin, then describe where the tab is now.

    Args:
        ctx: The action context.
        page: The tab that landed.
        verb: How the result starts, e.g. "navigated to".

    Returns:
        "<verb> <url>", then "; "-joined block and signed-out notes.

    Raises:
        ActionError: If the landing origin isn't allowed (the tab was cleared).
    """
    decision = ctx.policy.check_url(page.url)
    if not decision.is_allowed:
        landed = origin_of(page.url)
        await page.goto(BLANK_PAGE)
        raise ActionError(f"blocked: ended up on {landed} ({decision.reason}); the tab was cleared")
    parts = [f"{verb} {await shown_url(ctx, page.url)}", drain_block_note(ctx)]
    parts.append(await signed_out_note(ctx, page))
    return "; ".join(part for part in parts if part)
