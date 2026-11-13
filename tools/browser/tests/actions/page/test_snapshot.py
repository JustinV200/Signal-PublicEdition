"""The snapshot's untrusted wrapper (redaction is in test_reading.py's security test)."""

import pytest
from support.browser_helpers import ALLOWED_HOST

from browser_tool.actions import (
    UNTRUSTED_CLOSE,
    UNTRUSTED_OPEN,
    navigate,
    snapshot,
)


@pytest.mark.asyncio
async def test_page_text_cannot_close_the_untrusted_wrapper(make_ctx, fixture_server):
    ctx = await make_ctx()
    await navigate(ctx, fixture_server.url(ALLOWED_HOST, "/plain.html"))
    text = await snapshot(ctx)
    assert text.startswith(UNTRUSTED_OPEN)
    assert text.count(UNTRUSTED_CLOSE) == 1
    assert "&lt;/untrusted_page_content>" in text
