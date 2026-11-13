"""The find tool: search the tab's redacted snapshot for text, with refs and ancestors.

It searches the cached snapshot (taking one first if there is none, see
snapshot.cached_or_fresh), never the live page, so it can only ever show text a
snapshot would: password and code values are already redacted. Like every read
tool it refuses first a tab in Duo, then a page off the allowlist, then a page
the vault reports filled. Matching lines and their ancestor labels are page
text, so they are wrapped as untrusted content; the query is never echoed.
"""

from browser_tool.actions.context import ActionContext
from browser_tool.actions.errors import ActionError
from browser_tool.actions.guards import (
    ensure_no_filled_credentials,
    ensure_not_in_duo,
    ensure_page_allowed,
)
from browser_tool.actions.page.paging import Match, find_matches
from browser_tool.actions.page.snapshot import cached_or_fresh
from browser_tool.actions.untrusted import wrap_untrusted

DEFAULT_MAX_RESULTS = 20
MAX_RESULTS_CAP = 100
MAX_QUERY_CHARS = 200
BAD_TEXT = "bad text: give 1 to 200 characters to look for"
BAD_MAX_RESULTS = "bad max_results: use a number from 1 (at most 100)"
NO_MATCHES = "no matches in the latest snapshot of {url}"
SUMMARY = "{total} matching line(s) in the latest snapshot of {url}"
MORE_HINT = "; showing the first {shown}"
READ_HINT = ". snapshot(ref=...) shows what is under a ref, snapshot(page=N) a whole page."


async def find(ctx: ActionContext, text: str, max_results: int = DEFAULT_MAX_RESULTS) -> str:
    """Find the snapshot lines that contain `text` (case-insensitive).

    Args:
        ctx: The action context.
        text: What to look for.
        max_results: How many matching lines to show, capped at MAX_RESULTS_CAP.

    Returns:
        One line per match (line number, page, ref, ancestors and the line) in
        <untrusted_page_content>, then how many lines matched; or NO_MATCHES.

    Raises:
        ActionError: On bad arguments, a Duo tab, a refused page, or filled credentials.
    """
    query = text.strip()
    if not 0 < len(query) <= MAX_QUERY_CHARS:
        raise ActionError(BAD_TEXT)
    if max_results < 1:
        raise ActionError(BAD_MAX_RESULTS)
    limit = min(max_results, MAX_RESULTS_CAP)
    tab = await ctx.session.current_page()
    ensure_not_in_duo(ctx, tab)
    ensure_page_allowed(ctx, tab)
    await ensure_no_filled_credentials(ctx, tab)
    cached = await cached_or_fresh(ctx, tab)
    max_chars = ctx.settings.browser.max_snapshot_chars
    matches, total = find_matches(cached.text, query, max_chars, limit)
    url = cached.shown_url
    if not matches:
        return NO_MATCHES.format(url=url)
    listing = "\n".join(_describe(match) for match in matches)
    summary = SUMMARY.format(total=total, url=url)
    if total > len(matches):
        summary += MORE_HINT.format(shown=len(matches))
    return wrap_untrusted(f"\n{listing}\n") + "\n" + summary + READ_HINT


def _describe(match: Match) -> str:
    """One result line, e.g. 'line 42 (page 1) ref e12 in main > form "Compose": - button ...'."""
    parts = [f"line {match.line_no} (page {match.page})"]
    if match.ref is not None:
        parts.append(f"ref {match.ref}")
    if match.path:
        parts.append("in " + " > ".join(match.path))
    return " ".join(parts) + f": {match.text}"
