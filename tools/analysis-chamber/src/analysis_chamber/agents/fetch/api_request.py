"""is_api_request: whether a URL is a data-API call, which skips the robots.txt check.

robots.txt governs crawlers of web pages. Public data APIs often disallow `*` for their own
API paths (and some, like FRED's, never answer the robots.txt fetch), yet an API call with a
key or a JSON/CSV endpoint is the intended way to use them. The owner's rule: skip robots.txt
for API calls, keep honouring it for ordinary pages. Judged from the URL alone, because the
check runs before the request (so the response type isn't known yet).
"""

import re
from urllib.parse import parse_qsl, urlsplit

# Query parameter names (lowercased, "-" and "_" removed) that carry an API key.
_KEY_PARAMS = frozenset({"apikey", "key", "token", "accesskey", "accesstoken", "apitoken"})
# Query parameters that pick a data format, and the formats that mean "data, not a page".
_FORMAT_PARAMS = frozenset({"format", "filetype", "fmt", "output"})
_DATA_FORMATS = frozenset({"json", "csv"})
_DATA_FILE = re.compile(r"\.(json|csv)$", re.IGNORECASE)
# /api/ and /v<N>/ segments also appear in ordinary docs pages (MDN's .../Web/API/fetch,
# pandas' .../reference/api/pandas.DataFrame.html), so the segment rule doesn't count for a page
# extension or a docs-style path (/docs/, /reference/, /guide/). Kept deliberately simple.
_API_SEGMENT = re.compile(r"/api(/|$)|/v\d+(/|$)", re.IGNORECASE)
_PAGE_EXTENSION = re.compile(r"\.(html?|php|aspx)$", re.IGNORECASE)
_DOCS_SEGMENT = re.compile(r"/(docs|reference|guide)(/|$)", re.IGNORECASE)


def is_api_request(url: str) -> bool:
    """True if `url` is a data-API call: it carries an API key parameter, its path ends in
    .json or .csv or has an /api/ or /v<N>/ segment, or a format parameter asks for json/csv.
    """
    parts = urlsplit(url)
    if _DATA_FILE.search(parts.path) or _is_api_path(parts.path):
        return True
    for name, value in parse_qsl(parts.query, keep_blank_values=True):
        normalized = name.lower().replace("-", "").replace("_", "")
        if normalized in _KEY_PARAMS:
            return True
        if normalized in _FORMAT_PARAMS and value.lower() in _DATA_FORMATS:
            return True
    return False


def _is_api_path(path: str) -> bool:
    """True if the path has an /api/ or /v<N>/ segment and doesn't look like a docs page."""
    if not _API_SEGMENT.search(path):
        return False
    return not (_PAGE_EXTENSION.search(path) or _DOCS_SEGMENT.search(path))
