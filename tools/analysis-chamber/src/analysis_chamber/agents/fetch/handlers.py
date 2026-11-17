"""ChamberTools: what chamber_fetch, chamber_extract_file and chamber_search do.

The lead never gets raw HTML, text or search snippets. Pages go to the extractor
and only its checked extract comes back (framed, since it came from untrusted
text). Data files are saved under data/raw and come back as a path plus a short
head. Every fetch, good or failed, is reported through `on_source` for
manifest.sources. Failures fail closed: the lead gets an error result naming
the source and never the raw content (spec 7.2: skipped and noted).

No exception escapes a handler: the SDK would hand its text to the lead, and
that text can carry server or page content. Unexpected errors are logged here
and the lead gets fixed text with the exception's type name.
"""

import json
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import urlsplit

from signal_untrusted import framed

from analysis_chamber.agents.fetch.download import Download
from analysis_chamber.agents.fetch.http import FetchError
from analysis_chamber.agents.fetch.pages import data_suffix, is_data_file, page_text
from analysis_chamber.agents.fetch.store import save_extract, save_raw, source_record
from analysis_chamber.agents.nested import Extractor, Searcher
from analysis_chamber.guard import is_under

logger = logging.getLogger(__name__)

Downloader = Callable[[str], Awaitable[Download]]
# Gets each manifest.sources record.
SourceSink = Callable[[dict], None]
ToolResult = dict[str, Any]

HEAD_LINES = 5
HEAD_CHARS = 800
MAX_FILE_CHARS = 200_000
UNKNOWN_HOST = "unknown-host"
_TEXT_DATA_TYPES = ("json", "csv", "tab-separated")
EXTRACT_TAG = "untrusted_extract_content"
DATA_HEAD_TAG = "untrusted_data_content"
SEARCH_TAG = "untrusted_search_content"
WITHHELD = "extract failed; raw output withheld"


def result(text: str, is_error: bool = False) -> ToolResult:
    """An MCP tool result with one text block."""
    return {"content": [{"type": "text", "text": text}], "is_error": is_error}


def render_extract(extract: dict) -> str:
    """A checked extract as indented JSON, the form saved and shown to the lead."""
    return json.dumps(extract, indent=1, ensure_ascii=False)


def _host(url: str) -> str:
    """The URL's host[:port], or UNKNOWN_HOST if it has none or doesn't parse."""
    try:
        return urlsplit(url).netloc or UNKNOWN_HOST
    except ValueError:
        return UNKNOWN_HOST


@dataclass(frozen=True)
class ChamberIO:
    """The I/O ChamberTools uses, injected so tests can fake every outside call.

    Attributes:
        download: Fetches a URL (HttpDownloader).
        extract: The tool-less extractor (SdkExtractor).
        search: The WebSearch-only searcher (SdkSearcher).
    """

    download: Downloader
    extract: Extractor
    search: Searcher


class ChamberTools:
    """The chamber server's page, file and search logic for one run."""

    def __init__(self, run_dir: Path, io: ChamberIO, on_source: SourceSink) -> None:
        """Args: run_dir: the run folder; io: downloader, extractor and searcher;
        on_source: receives each manifest.sources record."""
        self._run_dir = run_dir
        self._io = io
        self._on_source = on_source

    async def fetch(self, url: str, instructions: str) -> ToolResult:
        """Fetch `url`: a data file is saved, a page is extracted. Never raises."""
        host = _host(url)
        try:
            download = await self._io.download(url)
            if is_data_file(download.url, download.content_type, download.body):
                return self._save_data(host, url, download)
            text = page_text(download.body, download.content_type)
        except FetchError as error:  # fixed text plus the lead's own URL
            return self._failed(host, url, f"fetch failed: {error}")
        except Exception as error:
            logger.warning("chamber_fetch of %s failed", url, exc_info=True)
            return self._failed(host, url, f"fetch failed ({type(error).__name__})")
        return await self._extracted(host, url, text, instructions)

    async def extract_file(self, path: str, instructions: str) -> ToolResult:
        """Run the extractor over a text file inside the run folder. Never raises."""
        try:
            file = (self._run_dir / path).resolve()
            if not is_under(file, self._run_dir) or not file.is_file():
                return result(f"refused: {path} is not a file inside the run folder", is_error=True)
            text = file.read_text(encoding="utf-8", errors="replace")[:MAX_FILE_CHARS]
        except Exception as error:  # OSError, or a path Windows can't resolve
            logger.warning("chamber_extract_file of %s failed", path, exc_info=True)
            return self._failed(path, path, f"read failed ({type(error).__name__})")
        return await self._extracted(file.stem, self._relative(file), text, instructions)

    async def search(self, query: str) -> ToolResult:
        """Web search through the WebSearch-only session: titles, URLs and dates only."""
        try:
            results = await self._io.search(query)
        except Exception:
            logger.warning("chamber_search failed", exc_info=True)
            return result("search failed; try another query", is_error=True)
        line = f"Results for {query!r} (read one with chamber_fetch):".replace("\n", " ")
        return result(framed(line, results, SEARCH_TAG))

    async def _extracted(self, label: str, source: str, text: str, instructions: str) -> ToolResult:
        """Extract `text`, save and record it. Fails closed on any error."""
        try:
            extract = await self._io.extract(source, text, instructions)
            path = save_extract(self._run_dir, label, source, render_extract(extract))
        except Exception as error:  # fail closed on anything, not just NestedError
            logger.warning("extract of %s failed", source, exc_info=True)
            return self._failed(label, source, f"{WITHHELD} ({type(error).__name__})")
        self._record(source_record(label, source, "ok", f"extract {self._relative(path)}"))
        line = f"Extract of {source}, saved to {self._relative(path)}:".replace("\n", " ")
        return result(framed(line, extract, EXTRACT_TAG))

    def _save_data(self, host: str, url: str, download: Download) -> ToolResult:
        """Save a data file to data/raw and describe it. Raises OSError.

        The file is named from the lead's URL, not the redirect target, so no
        server-chosen name reaches the lead.
        """
        name = PurePosixPath(urlsplit(url).path).name or f"{host}{data_suffix(url)}"
        relative = self._relative(save_raw(self._run_dir, name, download.body))
        self._record(source_record(host, url, "ok", f"data file {relative}"))
        kind = download.content_type or "unknown type"
        line = f"Saved {len(download.body)} bytes ({kind}) to {relative}."
        if not any(text_type in download.content_type for text_type in _TEXT_DATA_TYPES):
            return result(line)
        head = "\n".join(download.body.decode("utf-8", "replace").splitlines()[:HEAD_LINES])
        return result(framed(line + " First lines:", head[:HEAD_CHARS], DATA_HEAD_TAG))

    def _failed(self, name: str, source: str, note: str) -> ToolResult:
        """Record a failed source and tell the lead to skip it."""
        self._record(source_record(name, source, "failed", note))
        return result(f"{note}. Skip this source and note it in the caveats.", is_error=True)

    def _record(self, record: dict) -> None:
        """Pass `record` to on_source; a sink error is logged and never escapes a handler."""
        try:
            self._on_source(record)
        except Exception:
            logger.warning("on_source failed for %s", record.get("url"), exc_info=True)

    def _relative(self, path: Path) -> str:
        """`path` relative to the run folder, with forward slashes."""
        return path.resolve().relative_to(self._run_dir.resolve()).as_posix()
