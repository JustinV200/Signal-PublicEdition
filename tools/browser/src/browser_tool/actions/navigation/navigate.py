"""The navigate tool, and the policy check every URL the model opens goes through.

navigate() checks the policy before loading (checked_target, shared with
new_tab), reports redirect hops that were blocked, and, as a backstop, clears
the page if it still lands on a non-allowed origin (e.g. behind a proxy, where
DNS-level blocking doesn't apply; see signin.report_location, which also adds
the signed-out note on a login page). It lets the landing settle first
(nav_watch.NavigationWatch). A URL that starts a download is reported as one,
not as a failed load (load_failure.describe_load_failure). Page URLs shown to
the model drop query strings and fragments and are scrubbed (see
secret_scrub.shown_url). A tab with a dialog open is refused (answer it first).
"""

from urllib.parse import urlsplit

from playwright.async_api import Error as PlaywrightError

from browser_tool.actions.context import ActionContext
from browser_tool.actions.errors import ActionError
from browser_tool.actions.guards import ensure_no_dialog
from browser_tool.actions.navigation.load_failure import describe_load_failure
from browser_tool.actions.navigation.nav_watch import NavigationWatch, settle_max_s
from browser_tool.actions.signin import report_location
from browser_tool.policy import REASON_NOT_ALLOWLISTED, display_url, origin_of, scheme_of

DEFAULT_SCHEME = "https://"
NAVIGABLE_SCHEMES = frozenset({"http", "https"})
ALLOWLIST_HINT = "; the owner can add it to [policy] allow in {config}"


async def navigate(ctx: ActionContext, url: str) -> str:
    """Load `url` in the current tab ("https://" is added when no scheme is given)."""
    target = checked_target(ctx, url)
    page = await ctx.session.current_page()
    ensure_no_dialog(ctx, page)
    ctx.session.block_log.drain()
    downloads_before = ctx.session.downloads.started
    with NavigationWatch(page) as watch:
        try:
            await page.goto(target, wait_until="domcontentloaded")
        except PlaywrightError as error:
            return await describe_load_failure(
                ctx, page, error, downloads_before, display_url(target)
            )
        await watch.settle(settle_max_s(ctx))
    return await report_location(ctx, page, "navigated to")


def checked_target(ctx: ActionContext, url: str) -> str:
    """The URL to load for `url`, after the scheme, form and policy checks.

    Raises:
        ActionError: If the URL is malformed, not http(s), carries credentials,
            or its origin isn't allowed (with an allowlist hint).
    """
    target = _normalize_target(url)
    decision = ctx.policy.check_url(target)
    if not decision.is_allowed:
        is_hinted = decision.reason == REASON_NOT_ALLOWLISTED
        hint = ALLOWLIST_HINT.format(config=ctx.config_name) if is_hinted else ""
        raise ActionError(f"blocked: {origin_of(target)} is not allowed ({decision.reason}){hint}")
    return target


def _normalize_target(url: str) -> str:
    """Add a default scheme and refuse schemes and URL forms we never navigate to."""
    target = url.strip()
    if "://" not in target and scheme_of(target) not in ("about", "data", "javascript", "blob"):
        target = DEFAULT_SCHEME + target
    if scheme_of(target) not in NAVIGABLE_SCHEMES:
        raise ActionError("blocked: only http and https URLs can be opened")
    try:
        parts = urlsplit(target)
    except ValueError:
        raise ActionError("bad URL") from None
    if parts.username or parts.password:
        raise ActionError("blocked: URLs with embedded credentials are not allowed")
    if not parts.hostname:
        raise ActionError("bad URL: no host")
    return target
