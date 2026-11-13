"""Report finished downloads at the end of every tool call (browser_tool.downloads saves them).

A download can start from navigate, a click, a key press or the page itself,
and can start a moment after the action that caused it returns. So the tool
runner adds these notes to every result: downloads that finished during the
call, or before it, are reported once. Only downloads the call itself started
are waited for, so a slow older one can't hold up every later call. The file
name is page-supplied, so it and the path built from it are wrapped as untrusted
content.
"""

from browser_tool.actions.context import ActionContext
from browser_tool.actions.untrusted import wrap_untrusted

# How long a tool call waits for the downloads it started before reporting them as running.
FINISH_WAIT_S = 60.0


async def download_notes(ctx: ActionContext, started_before: int) -> list[str]:
    """One note per finished download, one for the rest still running.

    Args:
        ctx: The action context.
        started_before: ctx.session.downloads.started when the tool call began;
            only downloads started since then are waited for (up to FINISH_WAIT_S).

    Never raises (DownloadRecorder.collect doesn't).
    """
    finished, running = await ctx.session.downloads.collect(started_before, FINISH_WAIT_S)
    notes = []
    for download in finished:
        if download.path is None:
            shown = wrap_untrusted(download.original_name)
            notes.append(f"download not saved: {download.problem}: {shown}")
        else:
            shown = wrap_untrusted(f"{download.original_name} saved as {download.path}")
            notes.append(f"download saved ({download.size_bytes} bytes): {shown}")
    if running:
        notes.append(f"{running} download(s) still running; a later tool result reports them")
    return notes
