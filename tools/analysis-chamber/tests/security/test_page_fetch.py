"""Security table for page_fetch_hook: page fetches blocked, data downloads allowed."""
# ruff: noqa: E501 -- security tables keep one case per line so they read as tables

import email.message
import time
import urllib.error
import urllib.request

import pytest
from support.security_hooks import hook_input, is_deny

from analysis_chamber.security import head_check, page_fetch_hook
from analysis_chamber.security.page_fetch import fetch_block_reason
from analysis_chamber.security.rules.fetch_rules import MAX_HEAD_CHECKS

# The fake HEAD check: Content-Type per URL; anything else fails (None), which blocks.
CONTENT_TYPES = {
    "https://example.org/export": "text/csv; charset=utf-8",
    "https://example.org/article": "text/html",
}

# (tool name, tool input, allowed?)
FETCH_TABLE = [
    ("Bash", {"command": "curl -s https://example.org/news.html"}, False),
    ("Bash", {"command": "curl -sL https://example.org/about"}, False),  # HEAD fails
    ("Bash", {"command": "curl -o data/raw/x.csv https://example.org/x.csv"}, True),
    ("Bash", {"command": "wget https://example.org/dump.parquet?v=2"}, True),
    ("Bash", {"command": "curl https://example.org/export"}, True),  # HEAD says CSV
    ("Bash", {"command": "curl https://example.org/article"}, False),  # HEAD says HTML
    ("Bash", {"command": "curl https://example.org/notes.txt"}, False),
    ("Bash", {"command": "curl https://example.org/r?format=csv"}, True),
    ("Bash", {"command": "ls data/raw && python code/clean.py"}, True),
    ("PowerShell", {"command": "iwr https://example.org/page -OutFile p.html"}, False),
    ("PowerShell", {"command": "Invoke-WebRequest https://example.org/x.xlsx -OutFile x.xlsx"}, True),
    ("PowerShell", {"command": "irm 'https://api.stlouisfed.org/fred/series/observations?series_id=GDP'"}, True),
    ("Write", {"file_path": "code/w.py", "content": "import urllib.request\nurllib.request.urlopen('https://archive-api.open-meteo.com/v1/archive?latitude=0.0&longitude=0.0&daily=rain_sum')"}, True),  # live run 5
    ("Bash", {"command": "curl https://open-meteo.com/en/docs"}, False),
    ("PowerShell", {"command": "Start-BitsTransfer -Source https://example.org/blog"}, False),
    ("PowerShell", {"command": "$u = Get-Url; iwr $u"}, False),  # no literal URL
    ("Write", {"file_path": "code/get.py", "content": "import requests\nrequests.get('https://example.org/blog/post')"}, False),
    ("Write", {"file_path": "code/get.py", "content": "import requests\nr = requests.get('https://api.census.gov/data/2020/dec/pl?get=NAME')"}, True),
    ("Write", {"file_path": "code/get.py", "content": "import requests\nrequests.get(f'https://example.org/{page}')"}, False),
    ("Write", {"file_path": "code/t.py", "content": "import pandas as pd\npd.read_html('https://en.wikipedia.org/wiki/GDP')"}, False),
    ("Write", {"file_path": "code/t.py", "content": "from bs4 import BeautifulSoup\nBeautifulSoup(open('x.html'))"}, False),
    ("Write", {"file_path": "code/t.py", "content": "import pandas as pd\npd.read_csv('data/raw/x.csv')"}, True),
    ("Write", {"file_path": "code/t.py", "content": "import pandas as pd\npd.read_csv('https://example.org/x.csv')"}, True),
    ("Write", {"file_path": "code/y.py", "content": "import yfinance\nurl = 'https://query2.finance.yahoo.com/v8/finance/chart/SPY'\nimport httpx; httpx.get(url)"}, True),
    ("Write", {"file_path": "notes.md", "content": "curl https://example.org/blog"}, True),  # not a script
    ("Edit", {"file_path": "code/get.py", "old_string": "x", "new_string": "urllib.request.urlopen('https://example.org/')"}, False),
    ("Write", {"file_path": "code/h.py", "content": "requests.get('https://huggingface.co/meta-llama/model-card')"}, False),
    ("Write", {"file_path": "code/h.py", "content": "requests.get('https://huggingface.co/api/datasets/x/y')"}, True),
    # Fetches by import and call, however the library is named.
    ("Write", {"file_path": "code/get.py", "content": "import requests as rq\nrq.get('https://example.org/blog')"}, False),
    ("Write", {"file_path": "code/get.py", "content": "import requests as rq\nrq.get(url)"}, False),  # no literal URL
    ("Write", {"file_path": "code/get.py", "content": "from requests import get\nget('https://example.org/x.csv')"}, True),
    ("Bash", {"command": "python -c \"import httpx; httpx.get('https://example.org/blog')\""}, False),
    # Not fetches: a bare library name, a non-request call, a column value.
    ("PowerShell", {"command": "uv pip install httpx aiohttp"}, True),
    ("Write", {"file_path": "code/t.py", "content": "import urllib3\nurllib3.disable_warnings()"}, True),
    ("Write", {"file_path": "code/t.py", "content": "papers = df[df.kind == 'newspaper']"}, True),
    ("Write", {"file_path": "code/t.py", "content": "from selenium import webdriver\nwebdriver.Chrome()"}, False),
    ("Write", {"file_path": "code/t.py", "content": "from playwright.sync_api import sync_playwright"}, False),
    # A reader only fetches when a URL literal is its argument, not a citation string.
    ("Write", {"file_path": "code/fig.py", "content": "import pandas as pd\ndf = pd.read_csv('data/clean/u.csv')\nplt.figtext(0, 0, 'Source: https://fred.stlouisfed.org/series/UNRATE')"}, True),
    ("Write", {"file_path": "code/t.py", "content": "import pandas as pd\npd.read_json(\n    'https://example.org/blog')"}, False),
    # Chart captions and labels cite sources; their URLs aren't fetched.
    ("Write", {"file_path": "code/fig.py", "content": "import requests\nr = requests.get('https://api.stlouisfed.org/fred/series/observations?series_id=X')\nplt.figtext(0, 0, 'Source: https://fred.stlouisfed.org/series/X')"}, True),
    ("Write", {"file_path": "code/fig.py", "content": "import pandas as pd\ndf = pd.read_csv('https://api.census.gov/data/x?get=NAME')\nax.set_title('Data (ACS): https://www.census.gov/acs')"}, True),
    ("Write", {"file_path": "code/fig.py", "content": "import requests\nax.set_title(requests.get('https://example.org/blog').text)"}, False),
    # URLs in comments aren't fetched; a URL fragment isn't a comment.
    ("Write", {"file_path": "code/c.py", "content": "import requests\n# docs: https://example.org/blog/about\nrequests.get('https://example.org/x.csv')"}, True),
    ("PowerShell", {"command": "<# see https://example.org/page #>\niwr https://example.org/x.csv -OutFile x.csv"}, True),
    ("Bash", {"command": "curl -o x.csv https://example.org/x.csv  # from https://example.org/about"}, True),
    ("Bash", {"command": "curl https://example.org/page#top"}, False),
    # Edits are checked against the whole file after the edit (files in conftest).
    ("Edit", {"file_path": "code/old_fetch.py", "old_string": "x.csv", "new_string": "blog"}, False),
    ("Edit", {"file_path": "code/old_fetch.py", "old_string": "x.csv", "new_string": "y.parquet"}, True),
    ("MultiEdit", {"file_path": "code/new.py", "edits": [{"old_string": "a", "new_string": "U = 'https://example.org/blog'"}, {"old_string": "b", "new_string": "import requests\nrequests.get(U)"}]}, False),
    ("NotebookEdit", {"notebook_path": "code/old.ipynb", "cell_id": "c2", "new_source": "URL = 'https://example.org/blog'"}, False),
]  # fmt: skip


@pytest.mark.asyncio
@pytest.mark.parametrize(("tool", "tool_input", "allowed"), FETCH_TABLE)
async def test_page_fetch_hook(make_ctx, tool: str, tool_input: dict, allowed: bool) -> None:
    request = hook_input(tool, **tool_input)
    request["cwd"] = str(make_ctx().run_dir)  # relative edit paths start in the run folder
    output = await page_fetch_hook(request, "u", {}, checker=CONTENT_TYPES.get)
    assert is_deny(output) is not allowed
    if not allowed:
        assert "chamber_fetch" in output["hookSpecificOutput"]["permissionDecisionReason"]


def test_head_check_reads_content_type_from_an_http_error(monkeypatch) -> None:
    """A 405 to HEAD still says what the URL serves (regression: it counted as a page)."""
    headers = email.message.Message()
    headers["Content-Type"] = "application/json"

    def refuse(request, timeout):
        raise urllib.error.HTTPError(request.full_url, 405, "Method Not Allowed", headers, None)

    monkeypatch.setattr(urllib.request, "urlopen", refuse)
    assert head_check.head_content_type("https://api.example.gov/v1/series") == "application/json"


def _csv_after(delay_s: float):
    """A fake HEAD check that says CSV, after a delay."""

    def check(url: str) -> str:
        time.sleep(delay_s)
        return "text/csv"

    return check


@pytest.mark.parametrize(
    ("url_count", "delay_s", "allowed"),
    [(MAX_HEAD_CHECKS, 0.0, True), (MAX_HEAD_CHECKS + 1, 0.0, False), (1, 1.0, False)],
)
def test_head_checks_are_bounded(
    monkeypatch, url_count: int, delay_s: float, allowed: bool
) -> None:
    monkeypatch.setattr(head_check, "HEAD_DEADLINE_S", 0.2)
    urls = " ".join(f"https://example.org/export{n}" for n in range(url_count))
    reason = fetch_block_reason(f"curl {urls}", _csv_after(delay_s))
    assert (reason is None) is allowed
