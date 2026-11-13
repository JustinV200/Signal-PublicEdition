"""The read_download tool: the text of a saved PDF or plain-text download, as untrusted data.

Order of checks:
- the docker server refuses at once (ctx.downloads_readable): its downloads
  are refused anyway;
- the path goes through the same check as uploads (local_files): a plain
  drive path inside the downloads folder, judged lexically before anything
  touches the disk, with no link or junction on the way, read once;
- only .pdf files and a few plain-text types are read; anything else (an
  .exe, a .zip, an .html page) is refused, never opened;
- a PDF's text comes from pdf_text (pypdf in a child process, with a page
  cap per call and a time limit);
- the whole text is scrubbed of every tab's live secrets (scrub_or_refuse,
  fails closed), and only then cut at [browser] max_snapshot_chars, so a cut
  can't leave the start of a secret the scrub would no longer find; then it
  is wrapped as untrusted.
The file name is page-supplied, so it goes inside the wrapper too.
"""

import re
from pathlib import Path
from typing import NamedTuple

from browser_tool.actions.context import ActionContext
from browser_tool.actions.downloads.pdf_text import pdf_text
from browser_tool.actions.errors import ActionError
from browser_tool.actions.local_files import CheckedFile, read_checked_file
from browser_tool.actions.secret_scrub import scrub_or_refuse
from browser_tool.actions.untrusted import wrap_untrusted
from browser_tool.config import resolve_tool_path

BYTES_PER_MB = 1024 * 1024
# Bigger files are refused: the whole file is read into memory.
MAX_READ_MB = 50
MAX_PAGES_AT_ONCE = 20
PDF_SUFFIX = ".pdf"
TEXT_SUFFIXES = frozenset({".txt", ".csv", ".md", ".json", ".log"})
# "3" or "2-5", 1-based.
PAGES_RE = re.compile(r"(\d{1,6})(?:-(\d{1,6}))?")

READS_OFF = "refused: read_download is off in docker jobs (downloads are refused there)"
NOT_READABLE = "refused: read_download reads only .pdf, .txt, .csv, .md, .json and .log files"
NOT_TEXT = "refused: the file is not plain UTF-8 text"
BAD_PAGES = (
    f'bad pages: use one page ("3") or a range ("2-5") from 1, at most {MAX_PAGES_AT_ONCE} pages'
)
PAGES_FOR_PDF = "bad pages: pages is only for PDFs; leave it out for a text file"
NO_SUCH_PAGE = "no page {page}: the PDF has {total} page(s)"
CUT_NOTE = "; cut at {max_chars} characters"
PDF_CUT_HINT = ", ask for fewer pages to see the rest"
MORE_PAGES_HINT = '; read_download(path, pages="{first}-{last}") reads on'


class FileText(NamedTuple):
    """A file's whole text, before scrubbing and cutting.

    Attributes:
        body: The text.
        summary: What was read, e.g. "read pages 1-3 of 9".
        cut_hint: Added to CUT_NOTE when the text is cut.
        more_hint: Added when it isn't cut but there is more to read ("" if none).
        is_cut: True when the reader itself stopped early (the PDF's char cap).
    """

    body: str
    summary: str
    cut_hint: str = ""
    more_hint: str = ""
    is_cut: bool = False


async def read_download(ctx: ActionContext, path: str, pages: str | None = None) -> str:
    """Return the text of the downloaded file `path` (a PDF's pages, or a text file).

    Args:
        ctx: The action context.
        path: The file's full path, inside the downloads folder (as a download
            note gave it).
        pages: For a PDF, "N" or "N-M" (1-based, at most MAX_PAGES_AT_ONCE);
            default: the first MAX_PAGES_AT_ONCE pages.

    Returns:
        The text in <untrusted_page_content>, then what was read.

    Raises:
        ActionError: On the docker server, a refused path or file type, bad
            pages, or a PDF that can't be read.
    """
    if not ctx.downloads_readable:
        raise ActionError(READS_OFF)
    folder = resolve_tool_path(ctx.settings.downloads.folder)
    checked = read_checked_file(path, [folder], MAX_READ_MB * BYTES_PER_MB)
    max_chars = ctx.settings.browser.max_snapshot_chars
    suffix = Path(checked.name).suffix.lower()
    if suffix == PDF_SUFFIX:
        text = await _read_pdf(checked, pages, max_chars)
    elif suffix in TEXT_SUFFIXES:
        if pages is not None:
            raise ActionError(PAGES_FOR_PDF)
        text = _read_text(checked)
    else:
        raise ActionError(NOT_READABLE)
    # Scrub the whole text, then cut: half a secret would no longer be found.
    name, body = await scrub_or_refuse(ctx, [checked.name, text.body])
    summary = text.summary
    if text.is_cut or len(body) > max_chars:
        summary += CUT_NOTE.format(max_chars=max_chars) + text.cut_hint
    else:
        summary += text.more_hint
    return wrap_untrusted(f"\nfile: {name}\n{body[:max_chars]}\n") + "\n" + summary


async def _read_pdf(checked: CheckedFile, pages: str | None, max_chars: int) -> FileText:
    """The whole text of the asked-for pages, with 'read pages 1-3 of 9' and the hints.

    Raises:
        ActionError: BAD_PAGES, NO_SUCH_PAGE, or pdf_text's refusals.
    """
    first, last = _page_range(pages)
    extracted = await pdf_text(checked.data, first, last, max_chars)
    if first > extracted.total_pages:
        raise ActionError(NO_SUCH_PAGE.format(page=first, total=extracted.total_pages))
    read_to = first + len(extracted.pages) - 1
    body = "\n".join(
        f"--- page {first + offset} ---\n{text}" for offset, text in enumerate(extracted.pages)
    )
    more_hint = ""
    if read_to < extracted.total_pages:
        next_last = min(read_to + MAX_PAGES_AT_ONCE, extracted.total_pages)
        more_hint = MORE_PAGES_HINT.format(first=read_to + 1, last=next_last)
    summary = f"read pages {first}-{read_to} of {extracted.total_pages}"
    return FileText(body, summary, PDF_CUT_HINT, more_hint, extracted.is_cut)


def _page_range(pages: str | None) -> tuple[int, int]:
    """`pages` as (first, last), 1-based and inclusive.

    Raises:
        ActionError: BAD_PAGES.
    """
    if pages is None:
        return 1, MAX_PAGES_AT_ONCE
    match = PAGES_RE.fullmatch(pages.strip())
    if match is None:
        raise ActionError(BAD_PAGES)
    first = int(match.group(1))
    last = int(match.group(2) or first)
    if not 1 <= first <= last < first + MAX_PAGES_AT_ONCE:
        raise ActionError(BAD_PAGES)
    return first, last


def _read_text(checked: CheckedFile) -> FileText:
    """The whole decoded text.

    Raises:
        ActionError: NOT_TEXT for bytes that aren't UTF-8 or hold a NUL.
    """
    try:
        text = checked.data.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise ActionError(NOT_TEXT) from None
    if "\x00" in text:
        raise ActionError(NOT_TEXT)
    return FileText(text, f"read {len(text)} characters")
