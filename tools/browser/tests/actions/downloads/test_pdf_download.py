"""A PDF page is saved as a download, never shown in Edge's viewer, and reads back."""

import re
import time

import pytest
from support.browser_helpers import ALLOWED_HOST

from browser_tool.actions import navigate, read_download
from browser_tool.server import ToolRunner

# The viewer froze every tool for good; a download comes back in a few seconds.
QUICK_S = 10


@pytest.mark.asyncio
async def test_navigating_to_a_pdf_saves_it_as_a_download_and_read_download_reads_it(
    make_ctx, fixture_server
):
    ctx = await make_ctx()
    started = time.monotonic()
    result = await ToolRunner(ctx).run(
        "navigate", navigate, fixture_server.url(ALLOWED_HOST, "/report.pdf")
    )
    assert time.monotonic() - started < QUICK_S
    assert "started a download" in result and "download saved" in result, result
    saved = re.search(r"saved as (\S+\.pdf)", result).group(1)
    assert "second page text" in await read_download(ctx, saved, "2")
