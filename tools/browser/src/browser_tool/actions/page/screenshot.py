"""The screenshot tool: save a PNG of the tab, the whole page, or one element; return its path.

Like every read tool it refuses first a tab in Duo, then an open dialog or a
page off the allowlist (ensure_page_allowed), then a page the vault reports
filled, since a "show password" toggle or a filled username could otherwise
be visible. Sensitive fields (password/OTP) are painted over in every frame
with Playwright's mask option, whichever of the three shapes is taken.
"""

from datetime import datetime

from browser_tool.actions.context import ActionContext
from browser_tool.actions.errors import ActionError
from browser_tool.actions.guards import (
    ensure_no_filled_credentials,
    ensure_not_in_duo,
    ensure_page_allowed,
    ensure_ref_format,
    resolve_ref,
)
from browser_tool.config import resolve_tool_path
from browser_tool.redaction import sensitive_masks

FILE_NAME_FORMAT = "screenshot-%Y%m%d-%H%M%S-%f.png"
REF_OR_FULL_PAGE = "bad arguments: give ref (one element) or full_page=true, not both"


async def screenshot(ctx: ActionContext, ref: str | None = None, full_page: bool = False) -> str:
    """Capture the viewport, the whole page or one element to the screenshot folder.

    Args:
        ctx: The action context.
        ref: Capture only this element (a snapshot ref).
        full_page: Capture the whole scrollable page instead of the viewport.

    Returns:
        The PNG's path.

    Raises:
        ActionError: On bad arguments, a Duo tab, an open dialog, a refused
            page, filled credentials, or a ref that isn't on the page.
    """
    if ref is not None:
        if full_page:
            raise ActionError(REF_OR_FULL_PAGE)
        ensure_ref_format(ref)
    page = await ctx.session.current_page()
    ensure_not_in_duo(ctx, page)
    ensure_page_allowed(ctx, page)
    await ensure_no_filled_credentials(ctx, page)
    directory = resolve_tool_path(ctx.settings.browser.screenshot_dir)
    directory.mkdir(parents=True, exist_ok=True)
    path = str(directory / datetime.now().strftime(FILE_NAME_FORMAT))
    masks = sensitive_masks(page)
    if ref is None:
        await page.screenshot(path=path, full_page=full_page, mask=masks, animations="disabled")
    else:
        target = await resolve_ref(page, ref)
        await target.screenshot(path=path, mask=masks, animations="disabled")
    return path
