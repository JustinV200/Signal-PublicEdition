"""The credential tools: list_credentials and fill_login.

The vault fills the form itself; this module only passes the page and the
credential id, and returns "ok" or "failed: <code>". A third fill on the same
site within 10 minutes (a login loop, see signin.ensure_not_login_loop) is
refused before the vault is asked. Nothing a vault returns or raises is
echoed: exceptions become "failed: error" and only their type is logged.
"""

import logging
import re

from browser_tool.actions.context import ActionContext
from browser_tool.actions.errors import ActionError
from browser_tool.actions.guards import ensure_not_in_duo, ensure_page_allowed
from browser_tool.actions.signin import ensure_not_login_loop
from browser_tool.credentials import (
    FillResult,
    VaultUnavailableError,
    format_credentials,
    format_fill_result,
)
from browser_tool.policy import host_of, origin_of

logger = logging.getLogger(__name__)

CREDENTIAL_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")
ERROR_REASON = "error"


async def list_credentials(ctx: ActionContext) -> str:
    """List vault credentials (id, label, origins, username hint), or why there are none."""
    try:
        return format_credentials(ctx.filler.list_credentials())
    except VaultUnavailableError as error:
        return str(error)


async def fill_login(ctx: ActionContext, credential_id: str, submit: bool) -> str:
    """Have the vault fill the login form on the current page.

    Duo and the policy are checked here only, not again after the vault's own
    dialog: the call is the vault's from then on. The vault re-checks the page's
    and fields' origins on its own element handles right before it fills, so a
    tab that moved meanwhile isn't filled.

    TODO: a Duo iframe added to the same page while the vault's dialog is open
    doesn't stop the fill (it only touches the site's own login fields). Closing
    this needs a hook in the vault (tools/vault), e.g. a pre-fill callback the
    vault calls right before filling, so this side can run ensure_not_in_duo again.

    Returns:
        "ok", "failed: <reason code>", or the vault-unavailable message.

    Raises:
        ActionError: On a bad id, a Duo tab, a blocked page or a login loop.
    """
    if not CREDENTIAL_ID_RE.match(credential_id):
        raise ActionError("bad credential_id: use an id from list_credentials()")
    page = await ctx.session.current_page()
    ensure_not_in_duo(ctx, page)
    ensure_page_allowed(ctx, page)
    ensure_not_login_loop(ctx, page)
    site = host_of(page.url)
    try:
        result = await ctx.filler.fill_login(page, credential_id, submit=submit)
    except VaultUnavailableError as error:
        return str(error)
    except Exception as error:  # noqa: BLE001 - vault errors may carry secrets; never echo
        logger.error("vault fill_login raised %s", type(error).__name__)
        result = FillResult(ok=False, reason=ERROR_REASON)
    if result.ok and site is not None:
        ctx.session.login_loop.note_fill(site)
    text = format_fill_result(result)
    logger.info("fill_login %s on %s: %s", credential_id, origin_of(page.url), text)
    return text
