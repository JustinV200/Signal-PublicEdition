"""The tab tools: tabs (list them), switch_tab, new_tab and close_tab.

new_tab checks its URL with navigate's policy check before it opens anything,
then loads it through navigate itself (redirect, backstop and download handling
included).

Tab titles are page-supplied, so they are wrapped as untrusted content; a tab
frozen by an open dialog can't be asked for its title, so it shows
FROZEN_TITLE instead (session.read_until_dialog). URLs
drop query strings and fragments, with the path decoded and scrubbed (see
actions.secret_scrub.shown_url).
"""

from browser_tool.actions.context import ActionContext
from browser_tool.actions.errors import ActionError
from browser_tool.actions.navigation.navigate import checked_target, navigate
from browser_tool.actions.secret_scrub import shown_url
from browser_tool.actions.untrusted import wrap_untrusted
from browser_tool.session import read_until_dialog

MAX_TITLE_CHARS = 80
FROZEN_TITLE = "(unknown: a dialog is open on this tab)"


async def list_tabs(ctx: ActionContext) -> str:
    """One line per tab: index, current marker, URL and (untrusted, page-supplied) title."""
    current = await ctx.session.current_page()
    lines = []
    for index, page in enumerate(ctx.session.pages()):
        marker = " (current)" if page == current else ""
        is_read, title = await read_until_dialog(ctx.session.dialogs, page, page.title)
        shown = FROZEN_TITLE
        if is_read and title is not None:
            shown = wrap_untrusted(" ".join(title.split())[:MAX_TITLE_CHARS])
        url = await shown_url(ctx, page.url)
        lines.append(f"[{index}]{marker} {url} title: {shown}")
    return "\n".join(lines)


async def switch_tab(ctx: ActionContext, index: int) -> str:
    """Make tab `index` (from tabs()) the current tab.

    Raises:
        ActionError: If there is no such tab.
    """
    await ctx.session.start()
    try:
        page = await ctx.session.select_page(index)
    except IndexError as error:
        raise ActionError(str(error)) from None
    return f"switched to tab {index}: {await shown_url(ctx, page.url)}"


async def new_tab(ctx: ActionContext, url: str) -> str:
    """Open `url` in a new tab and make it the current tab.

    Raises:
        ActionError: If the URL fails navigate's checks (then no tab opens), or
            its load fails (the new tab stays open and current).
    """
    checked_target(ctx, url)  # refuse before a tab opens
    current = await ctx.session.current_page()
    page = await current.context.new_page()
    index = ctx.session.pages().index(page)
    await ctx.session.select_page(index)
    return f"opened tab {index}; {await navigate(ctx, url)}"


async def close_tab(ctx: ActionContext, index: int) -> str:
    """Close tab `index` (from tabs()); the current tab is then the last one if it was closed.

    Raises:
        ActionError: If there is no such tab, or it is the only one (closing it
            would close the browser window).
    """
    await ctx.session.start()
    pages = ctx.session.pages()
    if not 0 <= index < len(pages):
        raise ActionError(f"no tab {index}; there are {len(pages)} tabs")
    if len(pages) == 1:
        raise ActionError("refused: that is the only tab; navigate it somewhere else instead")
    await pages[index].close()
    current = await ctx.session.current_page()
    now = ctx.session.pages().index(current)
    return f"closed tab {index}; current tab is {now}: {await shown_url(ctx, current.url)}"
