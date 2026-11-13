"""The signed-out note, and the login-loop refusal that goes with it.

When navigate, back, click, press_key or wait_for_duo leaves the tab on a page
whose main frame shows a visible password field, the result gets one fixed
line telling the model it was signed out and may fill_login once. Only a
visible password field counts, so account choosers and SSO hand-off pages
never get the note. A tab with a dialog open gets none: it can't be read
until the dialog is answered. Callers let the landing settle first (see landing.py).

The session's LoginLoopGuard counts fills per site: a third fill_login on a
site within 10 minutes (a login plus one retry already used) is refused
(ensure_not_login_loop). The guard only refuses; nothing here fills, types or
clicks.

Only the page's hostname (or the owner's [duo] site_names name for it) is
shown, through duo.shown_site, never page text.
"""

import logging

from playwright.async_api import Error as PlaywrightError
from playwright.async_api import Page

from browser_tool.actions.context import ActionContext
from browser_tool.actions.errors import ActionError
from browser_tool.duo import shown_site
from browser_tool.policy import host_of

logger = logging.getLogger(__name__)

# Main frame only: page.locator doesn't look inside iframes.
VISIBLE_PASSWORD_SELECTOR = "input[type=password]:visible"
SIGNED_OUT_NOTE = (
    "signed out: this is {site}'s login page. If you have a credential for it, "
    "fill_login(id, submit=true) once, then wait_for_duo if Duo appears."
)
SIGNED_OUT_NO_VAULT_NOTE = (
    "signed out: this is {site}'s login page. This browser has no saved logins; "
    "tell the owner if you need to be signed in."
)
LOGIN_LOOP_NOTE = (
    "signed out: this is {site}'s login page, and it asked to sign in again right "
    "after a login. login loop: don't fill it again. Stop and tell the owner."
)
LOGIN_LOOP_REFUSAL = (
    "refused: login loop: fill_login already ran twice on {site} in the last 10 minutes "
    "and it asked to sign in again right after a login. Stop and tell the owner."
)


async def signed_out_note(ctx: ActionContext, page: Page) -> str:
    """The signed-out line for a page with a visible password field, or "" otherwise.

    Args:
        ctx: The action context.
        page: The tab, after its landing settled.

    Returns:
        SIGNED_OUT_NOTE (or its no-vault form), LOGIN_LOOP_NOTE once the site's
        fills are used up, or "" when the main frame shows no password field.
    """
    site = host_of(page.url)
    if ctx.session.dialogs.pending(page) is not None:
        return ""
    if site is None or not await _has_visible_password_field(page):
        return ""
    shown = shown_site(site, ctx.settings.duo.site_names)
    if ctx.session.login_loop.is_loop(site):
        return LOGIN_LOOP_NOTE.format(site=shown)
    note = SIGNED_OUT_NOTE if ctx.has_vault else SIGNED_OUT_NO_VAULT_NOTE
    return note.format(site=shown)


def ensure_not_login_loop(ctx: ActionContext, page: Page) -> None:
    """Refuse a third fill_login on the page's site within the guard's window.

    Raises:
        ActionError: With LOGIN_LOOP_REFUSAL when the site's fills are used up.
    """
    site = host_of(page.url)
    if site is not None and ctx.session.login_loop.is_loop(site):
        shown = shown_site(site, ctx.settings.duo.site_names)
        raise ActionError(LOGIN_LOOP_REFUSAL.format(site=shown))


async def _has_visible_password_field(page: Page) -> bool:
    """True when the main frame shows a visible input[type=password]."""
    try:
        return await page.locator(VISIBLE_PASSWORD_SELECTOR).count() > 0
    except PlaywrightError as error:
        # E.g. a navigation replaced the document mid-check. The note is only a hint.
        logger.info("login-page check failed (%s); no signed-out note", type(error).__name__)
        return False
