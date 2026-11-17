"""Tells data files from pages, and turns a page into plain text for the extractor.

Data files (spec 13: CSV, JSON, XLSX, API responses) may reach the lead as files.
HTML and other text must not, so anything text-like that isn't a known data
format counts as a page. The server's content type isn't trusted on its own: a
body that starts like markup is always a page, a JSON type must parse, and a
body with no type (or octet-stream) and no data extension is a page if it's text.
"""

import json
import re
from html.parser import HTMLParser
from pathlib import PurePosixPath
from urllib.parse import urlsplit

DATA_EXTENSIONS = frozenset(
    {
        *(".csv", ".tsv", ".json", ".jsonl", ".ndjson", ".geojson"),
        *(".xlsx", ".xls", ".parquet", ".feather", ".sqlite", ".db", ".dta", ".sav", ".shp"),
        *(".zip", ".gz", ".bz2", ".xz", ".7z", ".tar", ".pdf"),
    }
)
# PDFs count as data: there's no PDF text parser here. TODO: route PDF text through
# the extractor once the kit's PDF reader is wired in; until then the lead is told
# to convert to text and use chamber_extract_file.
JSON_CONTENT_TYPES = frozenset({"application/json", "application/geo+json"})
NDJSON_CONTENT_TYPE = "application/x-ndjson"
DATA_CONTENT_TYPES = frozenset(
    {
        *JSON_CONTENT_TYPES,
        NDJSON_CONTENT_TYPE,
        "text/csv",
        "text/tab-separated-values",
        "application/vnd.ms-excel",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/vnd.apache.parquet",
        "application/zip",
        "application/gzip",
        "application/pdf",
        "application/octet-stream",
    }
)
PAGE_CONTENT_TYPES = frozenset({"application/xhtml+xml", "application/xml", "application/rss+xml"})
# Types that say nothing about the body; the URL's extension or the body decides.
UNTYPED_CONTENT_TYPES = frozenset({"", "application/octet-stream"})
MAX_PAGE_CHARS = 200_000
# How much of the body the markup sniff looks at, and what it skips first.
_SNIFF_BYTES = 1024
_LEADING_JUNK = b"\xef\xbb\xbf \t\r\n\f"
_SKIPPED_TAGS = frozenset({"script", "style", "noscript", "template", "svg"})
_SPACES = re.compile(r"[ \t\r\f\v]+")
_BLANK_LINES = re.compile(r"\n\s*\n+")


def looks_like_markup(body: bytes) -> bool:
    """True if the body starts like HTML or XML (`<`, which covers `<!doctype` and `<html`)."""
    return body[:_SNIFF_BYTES].lstrip(_LEADING_JUNK).startswith(b"<")


def _parses_as_json(body: bytes, content_type: str) -> bool:
    """True if the body is non-empty valid JSON (for NDJSON, every non-blank line is)."""
    try:
        text = body.decode("utf-8-sig")
        documents = text.splitlines() if content_type == NDJSON_CONTENT_TYPE else [text]
        parsed = [json.loads(document) for document in documents if document.strip()]
    except ValueError:  # UnicodeDecodeError and JSONDecodeError are ValueErrors
        return False
    return bool(parsed)


def _is_text(body: bytes) -> bool:
    """True if the body is UTF-8 with no NUL bytes, i.e. prose rather than a binary file."""
    if b"\x00" in body:
        return False
    try:
        body.decode("utf-8")
    except UnicodeDecodeError:
        return False
    return True


def is_data_file(url: str, content_type: str, body: bytes) -> bool:
    """True if the download is a data file, False if it's a page to extract from."""
    if looks_like_markup(body):
        return False
    if content_type in JSON_CONTENT_TYPES or content_type == NDJSON_CONTENT_TYPE:
        return _parses_as_json(body, content_type)
    # No type and no data extension: text is a page, so prose can't land in data/raw/.
    if content_type in UNTYPED_CONTENT_TYPES and not data_suffix(url):
        return not _is_text(body)
    if content_type in DATA_CONTENT_TYPES:
        return True
    if content_type.startswith("text/") or content_type in PAGE_CONTENT_TYPES:
        return False
    # Unknown binary types are data unless the URL looks like a page.
    return PurePosixPath(urlsplit(url).path).suffix.lower() not in {".html", ".htm", ".txt"}


def data_suffix(url: str) -> str:
    """The URL's known data extension, or "" if it has none."""
    suffix = PurePosixPath(urlsplit(url).path).suffix.lower()
    return suffix if suffix in DATA_EXTENSIONS else ""


def page_text(body: bytes, content_type: str) -> str:
    """The page as plain text: tags, scripts and styles dropped, cut to MAX_PAGE_CHARS."""
    text = body.decode("utf-8", errors="replace")
    if "html" in content_type or "xml" in content_type or looks_like_markup(body):
        parser = _TextParser()
        parser.feed(text)
        parser.close()
        text = "".join(parser.parts)
    text = _BLANK_LINES.sub("\n\n", _SPACES.sub(" ", text)).strip()
    return text[:MAX_PAGE_CHARS]


class _TextParser(HTMLParser):
    """Collects text outside script/style-like tags, one block per line."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list) -> None:
        if tag in _SKIPPED_TAGS:
            self._skip_depth += 1
        elif tag in {"p", "div", "br", "li", "tr", "h1", "h2", "h3", "h4", "section"}:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in _SKIPPED_TAGS and self._skip_depth:
            self._skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if not self._skip_depth:
            self.parts.append(data)
