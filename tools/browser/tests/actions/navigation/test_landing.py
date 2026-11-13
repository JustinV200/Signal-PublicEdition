"""Navigation-aware settling after a click or key press (B4), on headless Edge.

The slow page answers 1.2 s late, longer than any fixed quiet spell, so a result
that names it proves the wait followed the navigation itself.
"""

import time

import pytest
from support.browser_helpers import ALLOWED_HOST, ref_for

from browser_tool.actions import click, navigate, press_key, snapshot
from browser_tool.actions.pointer.target import HOVER_SETTLE_MS

# A click that doesn't navigate must not wait for a landing (only for its
# fixed hover settle, which comes before the gate).
MAX_NO_NAVIGATION_S = 0.3 + HOVER_SETTLE_MS / 1000
# A 204 answer must end the wait well before the 10 s test navigation timeout.
MAX_NO_CONTENT_S = 2.0


@pytest.mark.asyncio
async def test_a_click_or_key_that_navigates_reports_the_page_it_landed_on(
    make_ctx, fixture_server
):
    ctx = await make_ctx()
    await navigate(ctx, fixture_server.url(ALLOWED_HOST, "/waits.html"))
    assert "/slow" in await click(ctx, ref_for(await snapshot(ctx), 'link "Slow page"'))

    await navigate(ctx, fixture_server.url(ALLOWED_HOST, "/waits.html"))
    await click(ctx, ref_for(await snapshot(ctx), 'textbox "Slow search"'))
    assert "/slow" in await press_key(ctx, "Enter")  # a search form: no owner dialog


@pytest.mark.asyncio
async def test_a_navigation_answered_204_does_not_wait_out_the_timeout(make_ctx, fixture_server):
    ctx = await make_ctx()
    await navigate(ctx, fixture_server.url(ALLOWED_HOST, "/waits.html"))
    await click(ctx, ref_for(await snapshot(ctx), 'textbox "No content search"'))
    started = time.monotonic()
    result = await press_key(ctx, "Enter")
    assert time.monotonic() - started < MAX_NO_CONTENT_S
    assert "/waits.html" in result  # a 204 leaves the tab where it was


@pytest.mark.asyncio
async def test_a_click_that_does_not_navigate_returns_at_once(make_ctx, fixture_server):
    ctx = await make_ctx()
    await navigate(ctx, fixture_server.url(ALLOWED_HOST, "/waits.html"))
    stay = ref_for(await snapshot(ctx), 'button "Stay here"')
    started = time.monotonic()
    result = await click(ctx, stay)
    assert time.monotonic() - started < MAX_NO_NAVIGATION_S
    assert "/waits.html" in result
