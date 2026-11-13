"""DuoWatch on headless Edge: one notice and one heads-up per prompt, rate-limited voice.

Duo is faked inside the browser (support.fake_duo) and time is a FakeClock. The
voice hub is a local asyncio server with a temp token file, or a missing token
file; the real hub and its token are never touched.
"""

import logging

import pytest
from support.browser_helpers import ALLOWED_HOST, ref_for
from support.fake_duo import (
    DUO_ORIGIN,
    HUB_TOKEN,
    NOTICE_MARK,
    FakeClock,
    follow_login_to_duo,
    start_with_fake_duo,
)

from browser_tool.actions import (
    UNTRUSTED_CLOSE,
    ActionError,
    click,
    fill_login,
    list_tabs,
    navigate,
    press_key,
    select_option,
    snapshot,
    type_text,
)
from browser_tool.config import DuoSettings
from browser_tool.duo import DUO_LOCKOUT_MESSAGE
from browser_tool.server import ToolRunner

ADD_DUO_IFRAME = (
    "document.body.append(Object.assign(document.createElement('iframe'), "
    f"{{id: 'duo', src: '{DUO_ORIGIN}/frame'}}))"
)
# Every tool that changes page state, with throwaway arguments: the lockout
# refuses before a ref or credential is even looked up.
ACTING_TOOLS = (
    (click, ("e1",)),
    (type_text, ("e1", "x")),
    (select_option, ("e1", "x")),
    (press_key, ("Tab",)),
    (fill_login, ("demo", False)),
)


@pytest.mark.asyncio
async def test_duo_iframe_speaks_once_pauses_actions_and_tells_the_model_once(
    make_ctx, fixture_server, fake_hub
):
    settings, received = fake_hub
    clock = FakeClock()
    ctx = await make_ctx(duo=settings)
    page = await start_with_fake_duo(ctx, clock)
    runner = ToolRunner(ctx)

    url = fixture_server.url(ALLOWED_HOST, "/duo_iframe.html")
    results = [await runner.run("navigate", navigate, url)]
    await page.wait_for_load_state("load")
    # Read-only tools still work while Duo is showing.
    results.append(await runner.run("snapshot", snapshot))
    results.append(await runner.run("tabs", list_tabs))
    [noticed] = [result for result in results if NOTICE_MARK in result]
    assert noticed.count(NOTICE_MARK) == 1
    assert f"Tab 0 is showing a Duo two-factor prompt for {ALLOWED_HOST}" in noticed
    assert noticed.rfind(UNTRUSTED_CLOSE) < noticed.index(NOTICE_MARK)

    for action, args in ACTING_TOOLS:
        with pytest.raises(ActionError) as refusal:
            await action(ctx, *args)
        assert str(refusal.value) == DUO_LOCKOUT_MESSAGE

    # The owner approved and the prompt went away: actions work again.
    async with page.expect_event("framedetached"):
        await page.evaluate("document.getElementById('duo').remove()")
    text = await snapshot(ctx)
    assert "clicked" in await click(ctx, ref_for(text, 'button "Continue"'))

    # Duo again after the same-prompt window: a new notice for the model, but the
    # owner isn't told again within min_heads_up_interval_s.
    clock.now = settings.same_prompt_window_s + 1
    async with page.expect_event("framenavigated", lambda f: f.url.startswith(DUO_ORIGIN)):
        await page.evaluate(ADD_DUO_IFRAME)
    assert NOTICE_MARK in await runner.run("tabs", list_tabs)

    await ctx.session.duo.drain()
    assert received == [
        {
            "source": "browser",
            "text": f"Duo push for {ALLOWED_HOST}, approve on your phone.",
            "priority": "urgent",
            "token": HUB_TOKEN,
            "ring_through": True,
        }
    ]


@pytest.mark.asyncio
async def test_top_level_duo_without_a_hub_gives_one_notice_per_prompt(
    make_ctx, fixture_server, tmp_path, caplog
):
    missing_hub = DuoSettings(hub_token_file=str(tmp_path / "no-hub-token"))
    clock = FakeClock()
    ctx = await make_ctx(duo=missing_hub)
    page = await start_with_fake_duo(ctx, clock)
    runner = ToolRunner(ctx)
    site = fixture_server.url(ALLOWED_HOST, "/plain.html")
    await runner.run("navigate", navigate, site)
    caplog.set_level(logging.INFO)

    for _ in range(2):
        # The site's login sends the tab to Duo, which hops once inside Duo.
        await follow_login_to_duo(page, "/authorize")
        await page.wait_for_url(f"{DUO_ORIGIN}/prompt")
        result = await runner.run("tabs", list_tabs)
        assert result.count(NOTICE_MARK) == 1
        assert f"Duo two-factor prompt for {ALLOWED_HOST}" in result
        with pytest.raises(ActionError, match="only the owner may answer"):
            await click(ctx, "e1")
        # Leaving is allowed, and the hub being down never touches a result.
        assert "navigated to" in await runner.run("navigate", navigate, site)
        clock.now += missing_hub.min_heads_up_interval_s + 1

    await ctx.session.duo.drain()
    assert caplog.text.count("Voice hub not running") == 2


@pytest.mark.asyncio
async def test_a_page_that_keeps_re_adding_duo_leaves_one_pending_notice(make_ctx, fixture_server):
    clock = FakeClock()
    ctx = await make_ctx()
    page = await start_with_fake_duo(ctx, clock)
    await navigate(ctx, fixture_server.url(ALLOWED_HOST, "/duo_iframe.html"))
    await page.wait_for_load_state("load")

    # Each return to Duo is past the same-prompt window, so each is a new prompt.
    for _ in range(3):
        async with page.expect_event("framedetached"):
            await page.evaluate("document.getElementById('duo').remove()")
        clock.now += ctx.settings.duo.same_prompt_window_s + 1
        async with page.expect_event("framenavigated", lambda f: f.url.startswith(DUO_ORIGIN)):
            await page.evaluate(ADD_DUO_IFRAME)

    assert len(await ctx.session.duo.take_notices()) == 1
