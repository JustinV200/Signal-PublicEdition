"""PreToolUse hook that keeps raw web pages out of the lead (spec 13, decision 47).

It reads shell commands (Bash, PowerShell) and script files being written (.py, .ps1,
.sh, ...), with comments and chart-caption URLs stripped first. Code that fetches is
allowed only when every URL in it is a data download (head_check.page_urls). Everything
else is denied with a pointer to mcp__chamber__chamber_fetch. Page scraping libraries
are always denied.

Known gaps (risk accepted in spec section 20):
TODO: obfuscated or indirect code slips through: URLs assembled at run time in another
file, base64'd commands, a helper module with the URL in a variable called from a file
with no fetch call, R or other languages not in SCRIPT_SUFFIXES, ftp:// URLs.
"""

import asyncio
import re
from pathlib import Path
from typing import Any

from analysis_chamber.security.common import allow, code_text, deny
from analysis_chamber.security.head_check import (
    ContentTypeChecker,
    head_content_type,
    page_urls,
)
from analysis_chamber.security.rules.fetch_rules import (
    CAPTION_CALLS,
    HTTP_CALLS,
    HTTP_IMPORTS,
    HTTP_MODULE_CALLS,
    NETWORK_MARKERS,
    SCRAPING_MARKERS,
    URL_PATTERN,
    URL_READERS,
)

_USE_CHAMBER_FETCH = (
    "Pages and text must go through mcp__chamber__chamber_fetch(url, instructions), "
    "which returns an extract. Direct downloads are only for data files (CSV, JSON, "
    "XLSX, Parquet, archives) and data APIs."
)

_CITATIONS_ELSEWHERE = (
    "Every URL in a fetching script is checked, so if some are only citations, keep "
    "them in sources.json or another file, not in the fetch script. "
)

# PowerShell block comments, and `#` line comments (Python, PowerShell, sh) at a line
# start or after whitespace, so a URL fragment (`page#top`) isn't cut.
# shortcut: a ` #` inside a string also cuts the rest of its line; fine for a
# non-hostile agent, revisit if real code trips it.
_BLOCK_COMMENT = re.compile(r"<#.*?#>", re.DOTALL)
_LINE_COMMENT = re.compile(r"(?:^|(?<=\s))#.*$", re.MULTILINE)


def strip_comments(code: str) -> str:
    """Code with its `#` and `<# #>` comments removed, so URLs in them aren't checked."""
    return _LINE_COMMENT.sub("", _BLOCK_COMMENT.sub(" ", code))


def _strip_caption_urls(code: str) -> str:
    """Code with URLs removed from chart captions and labels (`plt.figtext('Source: ...')`).

    A source URL in a figure caption is a citation, so a fetch of a data API in the
    same script isn't denied for it.
    """
    return CAPTION_CALLS.sub(lambda call: URL_PATTERN.sub("", call.group(0)), code)


def _fetches(code: str, has_urls: bool) -> bool:
    """Whether code reaches the network: a fetch command, an HTTP call, or a URL reader."""
    if NETWORK_MARKERS.search(code) or HTTP_MODULE_CALLS.search(code):
        return True
    if HTTP_IMPORTS.search(code) and (has_urls or HTTP_CALLS.search(code)):
        return True
    return URL_READERS.search(code) is not None


def fetch_block_reason(code: str, checker: ContentTypeChecker) -> str | None:
    """Why a piece of code must not run, or None when it's fine.

    Args:
        code: A shell command or script text.
        checker: Content-Type lookup for ambiguous URLs.

    Returns:
        The deny reason, or None to allow.
    """
    code = _strip_caption_urls(strip_comments(code))
    if SCRAPING_MARKERS.search(code):
        return "Page scraping (read_html, BeautifulSoup, browsers) is blocked. " + (
            _USE_CHAMBER_FETCH
        )
    urls = URL_PATTERN.findall(code)
    if not _fetches(code, bool(urls)):
        return None
    if not urls:
        return (
            "This code fetches from the network but has no literal URL to check. Put the "
            "full data URL in the code. " + _USE_CHAMBER_FETCH
        )
    pages = page_urls(urls, checker)
    if not pages:
        return None
    reason = f"Not a data download (or not checked in time): {', '.join(pages)}. "
    if len(pages) < len(set(urls)):  # some URLs are data: the rest may only be citations
        reason += _CITATIONS_ELSEWHERE
    return reason + _USE_CHAMBER_FETCH


async def page_fetch_hook(
    hook_input: dict[str, Any],
    tool_use_id: str | None,
    context: Any,
    *,
    checker: ContentTypeChecker = head_content_type,
) -> dict[str, Any]:
    """PreToolUse hook (SDK HookCallback signature, `checker` bound by build_hooks).

    Args:
        hook_input: The SDK's PreToolUseHookInput (`tool_name`, `tool_input`, `cwd`).
        tool_use_id: Unused.
        context: Unused (SDK HookContext).
        checker: Content-Type lookup; the HEAD requests run in worker threads.

    Returns:
        A deny output for page fetches, else an empty output.
    """
    base_dir = Path(str(hook_input.get("cwd") or "."))
    tool_input = hook_input.get("tool_input") or {}
    code = code_text(str(hook_input.get("tool_name", "")), tool_input, base_dir)
    if not code:
        return allow()
    reason = await asyncio.to_thread(fetch_block_reason, code, checker)
    return deny(reason) if reason else allow()
