"""describe_load_failure: what a failed page load means, for navigate and the history steps.

Playwright fails goto, go_back, go_forward and reload with "Download is
starting" when the URL turned into a download: that is reported as one, not as
a failure (the tool runner adds the saved file). Otherwise the error is a
blocked hop (the request guard recorded it) or a plain failure, described
without the raw Playwright text.
"""

from playwright.async_api import Error as PlaywrightError
from playwright.async_api import Page

from browser_tool.actions.context import ActionContext
from browser_tool.actions.errors import ActionError, describe_playwright_error
from browser_tool.actions.guards import drain_block_note
from browser_tool.actions.secret_scrub import shown_url

# Playwright's load error when the URL turned into a download.
DOWNLOAD_STARTING = "Download is starting"
# The download event follows that error by a few milliseconds.
DOWNLOAD_START_WAIT_S = 5.0


async def describe_load_failure(
    ctx: ActionContext, page: Page, error: PlaywrightError, downloads_before: int, what: str
) -> str:
    """Return the download note when `error` was a download starting; raise otherwise.

    Args:
        ctx: The action context.
        page: The tab that tried to load.
        error: The load's Playwright error (only the fixed marker is read, never shown).
        downloads_before: ctx.session.downloads.started before the load.
        what: What loaded, for the note, e.g. a display URL or "going back".

    Raises:
        ActionError: "blocked: ..." for a blocked hop, else "navigation failed: ...".
    """
    if DOWNLOAD_STARTING in str(error) and await ctx.session.downloads.wait_for_start(
        downloads_before, DOWNLOAD_START_WAIT_S
    ):
        return f"{what} started a download; still at {await shown_url(ctx, page.url)}"
    block_note = drain_block_note(ctx)
    if block_note:
        raise ActionError(f"blocked: {block_note}")
    raise ActionError(f"navigation failed: {describe_playwright_error(error)}")
