"""The page-fetch hook's data: what counts as a fetch, and what counts as a data download.

Decision 47 in the spec: the lead may download data files itself, but HTML and text
pages must go through mcp__chamber__chamber_fetch so it only ever sees extracts.
Tune these lists here; page_fetch.py and head_check.py hold the logic.
"""

import re

from analysis_chamber.security.common import STATEMENT_START

# Shell and .NET calls that reach the network. A match plus a URL literal means the URLs
# get checked; a match with no URL literal at all is blocked (the URL can't be checked).
NETWORK_MARKERS = re.compile(
    r"\b(curl|wget|Invoke-WebRequest|Invoke-RestMethod|iwr|irm|Start-BitsTransfer"
    r"|DownloadString|DownloadFile|WebClient|HttpClient|urlopen|urlretrieve"
    r"|socket\.create_connection)\b",
    re.IGNORECASE,
)

# Python HTTP libraries, by import (`import requests as rq`, `from httpx import get`,
# also after `;` or the opening quote of `python -c "..."`). A bare mention
# (`uv pip install httpx`) doesn't count.
HTTP_IMPORTS = re.compile(
    rf"{STATEMENT_START}(?:import|from)\s+(?:requests|httpx|urllib3|aiohttp|urllib\.request"
    r"|http\.client)\b|\bimport\s+urllib\.request\b",
    re.MULTILINE,
)
# A request call on the library itself (`requests.get(`), which fetches with or without
# an import in sight (it may sit in another file).
HTTP_MODULE_CALLS = re.compile(
    r"\b(?:requests|httpx|aiohttp|urllib3)\.(?:\w+\.)*(?:get|post|put|patch|head|request"
    r"|stream|Session|Client|AsyncClient|ClientSession|PoolManager)\s*\("
)
# With an HTTP import, these calls fetch even when no URL literal is in sight.
# `urllib3.disable_warnings()` and other non-request calls don't match.
HTTP_CALLS = re.compile(
    r"\b(?:get|post|put|patch|head|request|urlopen|stream|Session|Client|AsyncClient"
    r"|PoolManager|ClientSession|HTTPS?Connection)\s*\("
)

# Readers that fetch when handed a URL literal as their argument
# (`pd.read_csv('https://...')`). They mostly read local files, so a reader of a local
# file in a script that also holds a citation URL isn't a fetch.
URL_READERS = re.compile(
    r"\b(?:read_csv|read_json|read_excel|read_parquet|read_table|read_xml|load_dataset)"
    r"\(\s*[rbfu]{0,2}['\"]https?://|\bImport-Csv\s+(?:-Path\s+)?['\"]?https?://",
    re.IGNORECASE,
)

# Page scraping: always blocked, whatever the URL, since it means raw HTML in the lead.
# Imports and calls only, so a column value like 'newspaper' doesn't count.
SCRAPING_MARKERS = re.compile(
    r"\bread_html\s*\(|\bBeautifulSoup\s*\(|\b(?:import|from)\s+(?:bs4|html2text|trafilatura"
    r"|newspaper|playwright|selenium|lxml\.html)\b|\bfrom\s+lxml\s+import\s+html\b"
    r"|\bselenium\.webdriver\b|\bplaywright\s+(?:install|codegen|open)\b|\.ParsedHtml\b",
    re.IGNORECASE,
)

# Chart captions and labels, where a URL is a citation, not a fetch: the call's
# arguments up to the first paren outside a string literal (they may span lines), or a
# `title=` / `caption=` keyword's string.
CAPTION_CALLS = re.compile(
    r"(?:\b(?:figtext|suptitle|annotate|set_title|set_xlabel|set_ylabel|xlabel|ylabel"
    r"|title)|\.text)\s*\((?:'[^'\n]*'|\"[^\"\n]*\"|[^()'\"])*"
    r"|[(,]\s*(?:title|caption)\s*=\s*[rfbu]{0,2}(?:'[^'\n]*'|\"[^\"\n]*\")"
)

URL_PATTERN = re.compile(r"https?://[^\s'\"<>`)\]]+", re.IGNORECASE)

# Signs a URL is built at run time (f-string, PowerShell var, %-format), so a HEAD
# check would hit the wrong address.
TEMPLATE_MARKERS = re.compile(r"[{}$]|%s|%\(")

# Path suffixes of data files. .xml, .txt, .pdf and .html are left out on purpose: they
# are usually feeds, prose or pages, so they go to the content-type check or chamber_fetch.
DATA_SUFFIXES = (
    ".csv", ".tsv", ".json", ".jsonl", ".ndjson", ".geojson",
    ".xlsx", ".xls", ".parquet", ".feather", ".arrow", ".dta", ".sav", ".sas7bdat",
    ".h5", ".hdf5", ".nc", ".npy", ".npz", ".sqlite", ".db", ".shp",
    ".zip", ".gz", ".bz2", ".xz", ".7z", ".tar", ".tgz",
)  # fmt: skip

# Query strings that ask an API for a data format (e.g. ?format=csv, &file_type=json).
DATA_QUERY = re.compile(
    r"(^|&)(format|file_type|fmt|output|outputformat)=(csv|tsv|json|xlsx?)\b", re.IGNORECASE
)

# Known data API hosts, matched in full against "host/path" (host lowercased).
DATA_HOSTS = tuple(
    re.compile(pattern)
    for pattern in (
        r"api\.stlouisfed\.org/.*",  # FRED API
        r"query\d*\.finance\.yahoo\.com/.*",  # yfinance
        r"datasets-server\.huggingface\.co/.*",
        r"huggingface\.co/(api/.*|datasets/[^/]+/[^/]+/resolve/.*)",  # not model/dataset pages
        r"(www\.)?kaggle\.com/api/.*",
        r"api\.census\.gov/.*",
        r"api\.worldbank\.org/.*",
        r"api\.bls\.gov/.*",
        r"api\.eia\.gov/.*",
        r"data\.sec\.gov/.*",
        # Open-Meteo's JSON APIs (api., archive-api., historical-forecast-api., ...):
        # keyless, and its servers don't answer HEAD in time (live run 5).
        r"([\w-]+-)?api\.open-meteo\.com/v1/.*",
    )
)

# Content types that are data, for the HEAD check of ambiguous URLs.
DATA_CONTENT_TYPES = (
    "text/csv", "text/tab-separated-values", "application/json", "application/x-ndjson",
    "application/vnd.ms-excel", "application/vnd.openxmlformats-officedocument.spreadsheetml",
    "application/vnd.apache.parquet", "application/zip", "application/gzip",
    "application/x-gzip", "application/octet-stream", "application/x-tar",
)  # fmt: skip

HEAD_TIMEOUT_S = 5.0
# A command or script gets at most this many HEAD checks, all within this total time;
# URLs left unchecked count as pages, so the fetch is denied. Keep the deadline well
# under the hook timeout (hooks.SECURITY_HOOK_TIMEOUT_S), or the SDK gives up first.
MAX_HEAD_CHECKS = 5
HEAD_DEADLINE_S = 12.0
