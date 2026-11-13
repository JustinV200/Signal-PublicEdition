"""Relaying Duo's Verified Push code (read only), on headless Edge with a fake Duo and hub.

Only top-level Duo prompts that an allowlisted site's own page sent the tab to,
only Duo frames nested purely in Duo, only one clear code, never through
history, at most once per prompt, and at most one relay per site per
min_heads_up_interval_s. The voice hub is the fake from conftest.py or a missing
token file; the real hub and its token are never touched. Redirect chains
through other hosts can't be served here (redirect hops skip routing and the
fake Duo host fails DNS), so test_prompt_state covers them.
"""

from dataclasses import replace

import pytest
from support.browser_helpers import ALLOWED_HOST, OTHER_HOST
from support.fake_duo import (
    DUO_ORIGIN,
    NOTICE_MARK,
    FakeClock,
    follow_login_to_duo,
    start_with_fake_duo,
)

from browser_tool.actions import list_tabs, navigate
from browser_tool.config import DuoSettings
from browser_tool.server import ToolRunner

# Relay on the test site, polling fast so the tests stay quick.
RELAY = {
    "code_relay_sites": (ALLOWED_HOST,),
    "code_relay_timeout_s": 5.0,
    "code_poll_interval_s": 0.05,
}
CODE_TEXT = "verification code"
# The page swaps itself for a blob: page of its own that embeds Duo. A tab's
# opener can do the same to a tab on an allowlisted site.
GO_TO_BLOB_WITH_DUO = (
    "location = URL.createObjectURL(new Blob("
    f"[\"<iframe src='{DUO_ORIGIN}/code-now'></iframe>\"], {{type: 'text/html'}}))"
)
ADD_OTHER_HOST_FRAME = (
    "(src) => document.body.append(Object.assign(document.createElement('iframe'), {src}))"
)


async def _show_top_level_duo(ctx, fixture_server, path: str) -> None:
    """Open the test site, then follow its login to the fake Duo page at `path`."""
    await navigate(ctx, fixture_server.url(ALLOWED_HOST, "/plain.html"))
    await follow_login_to_duo(await ctx.session.current_page(), path)


@pytest.mark.asyncio
async def test_a_code_shown_late_is_told_once_per_prompt_and_once_per_site_interval(
    make_ctx, fixture_server, fake_hub
):
    hub_settings, received = fake_hub
    relay_both = {**RELAY, "code_relay_sites": (ALLOWED_HOST, OTHER_HOST)}
    ctx = await make_ctx(allow=(ALLOWED_HOST, OTHER_HOST), duo=replace(hub_settings, **relay_both))
    clock = FakeClock()
    page = await start_with_fake_duo(ctx, clock)
    runner = ToolRunner(ctx)

    # Three prompts, all inside min_heads_up_interval_s of each other.
    results = []
    for host in (OTHER_HOST, ALLOWED_HOST, ALLOWED_HOST):
        await runner.run("navigate", navigate, fixture_server.url(host, "/plain.html"))
        clock.now += ctx.settings.duo.same_prompt_window_s + 1  # each one a new prompt
        # The site's login goes to Duo, which shows the code 300 ms later.
        await follow_login_to_duo(page, "/code")
        await ctx.session.duo.drain()
        results.append(await runner.run("tabs", list_tabs))

    # One pending notice per tab: the code's notice replaced the prompt's first one.
    assert [result.count(NOTICE_MARK) for result in results] == [1, 1, 1]
    for result in results[:2]:
        assert f"{CODE_TEXT} 482" in result
        assert "include it in any PushNotification" in result
    # The third prompt is the second for allowed.localhost within the interval.
    assert "482" not in results[2]
    assert "it was not relayed" in results[2]
    assert "PushNotification" not in results[2]
    await ctx.session.duo.drain()
    assert [note["text"] for note in received] == [
        f"Duo push for {OTHER_HOST}, approve on your phone.",
        f"Duo code for {OTHER_HOST}: 4 8 2. Type it in Duo Mobile and approve.",
        # The second prompt's heads-up was rate-limited; its code, the first for
        # this site, still goes out. The third prompt's is capped per site.
        f"Duo code for {ALLOWED_HOST}: 4 8 2. Type it in Duo Mobile and approve.",
    ]
    assert {note["priority"] for note in received} == {"urgent"}
    assert {note["source"] for note in received} == {"browser"}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "duo",
    [
        DuoSettings(),  # the default: no sites, so nothing is ever relayed
        DuoSettings(code_relay_sites=(OTHER_HOST,), code_poll_interval_s=0.05),
    ],
)
async def test_no_code_is_relayed_for_a_site_not_in_the_allowlist(make_ctx, fixture_server, duo):
    ctx = await make_ctx(duo=duo)
    page = await start_with_fake_duo(ctx, FakeClock())
    await _show_top_level_duo(ctx, fixture_server, "/code")
    await page.get_by_text("482").wait_for()

    await ctx.session.duo.drain()
    [notice] = await ctx.session.duo.take_notices()
    assert CODE_TEXT not in notice


async def _decoy_frame_inside_the_prompt(ctx, page, server, clock) -> None:
    # The decoy frame shows 482 from the start, before Duo's own 913: reading it
    # would relay 482, or nothing once both show.
    await _show_top_level_duo(ctx, server, "/code-with-decoy")


async def _two_different_codes(ctx, page, server, clock) -> None:
    await _show_top_level_duo(ctx, server, "/two-codes")


async def _outside_opener_sends_the_site_to_duo(ctx, page, server, clock) -> None:
    # A page off the allowlist opens the site in a popup, then sends that popup to Duo.
    site = server.url(ALLOWED_HOST, "/plain.html")
    await navigate(ctx, server.url(OTHER_HOST, "/plain.html"))
    async with page.expect_popup() as opened:
        await page.evaluate("(url) => { window.siteTab = window.open(url); }", site)
    popup = await opened.value
    await popup.wait_for_url(site)
    async with popup.expect_navigation(url=f"{DUO_ORIGIN}/code-now"):
        await page.evaluate(f"window.siteTab.location = '{DUO_ORIGIN}/code-now'")


async def _third_party_frame_gone_to_duo(ctx, page, server, clock) -> None:
    # The allowlisted page embeds another host's frame, which sends itself to Duo.
    await navigate(ctx, server.url(ALLOWED_HOST, "/plain.html"))
    async with page.expect_event("framenavigated", lambda f: OTHER_HOST in f.url) as loaded:
        await page.evaluate(ADD_OTHER_HOST_FRAME, server.url(OTHER_HOST, "/plain.html"))
    third_party = await loaded.value
    async with page.expect_event("framenavigated", lambda f: f.url.startswith(DUO_ORIGIN)):
        await third_party.evaluate(f"location = '{DUO_ORIGIN}/code-now'")


async def _page_with_no_host_embedding_duo(ctx, page, server, clock) -> None:
    # Regression: the blob: page used to borrow the allowlisted site's name.
    await navigate(ctx, server.url(ALLOWED_HOST, "/plain.html"))
    async with page.expect_event("framenavigated", lambda f: f.url.startswith(DUO_ORIGIN)):
        await page.evaluate(GO_TO_BLOB_WITH_DUO)


async def _back_to_duo_through_history(ctx, page, server, clock) -> None:
    # Visit the prompt and leave before its code shows (300 ms), then go back to it.
    site = server.url(ALLOWED_HOST, "/plain.html")
    await navigate(ctx, site)
    await follow_login_to_duo(page, "/code")
    await page.goto(site)
    clock.now += ctx.settings.duo.same_prompt_window_s + 1
    await page.go_back()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("show_prompt", "relayed_code"),
    [
        pytest.param(_decoy_frame_inside_the_prompt, "913", id="non-Duo frame in the prompt"),
        pytest.param(_two_different_codes, None, id="two codes"),
        pytest.param(_outside_opener_sends_the_site_to_duo, None, id="outside opener"),
        pytest.param(_third_party_frame_gone_to_duo, None, id="third-party frame gone to Duo"),
        pytest.param(_page_with_no_host_embedding_duo, None, id="blob page embedding Duo"),
        pytest.param(_back_to_duo_through_history, None, id="Duo reached through history"),
    ],
)
async def test_only_one_clear_code_on_a_fresh_top_level_duo_prompt_is_relayed(
    make_ctx, fixture_server, show_prompt, relayed_code
):
    relay_quick = {**RELAY, "code_relay_timeout_s": 1.0}
    ctx = await make_ctx(allow=(ALLOWED_HOST, OTHER_HOST), duo=DuoSettings(**relay_quick))
    clock = FakeClock()
    page = await start_with_fake_duo(ctx, clock)
    await show_prompt(ctx, page, fixture_server, clock)
    await page.wait_for_load_state("load")

    await ctx.session.duo.drain()
    notices = await ctx.session.duo.take_notices()
    if relayed_code is None:
        assert all(CODE_TEXT not in notice for notice in notices)
    else:
        assert any(f"{CODE_TEXT} {relayed_code}" in notice for notice in notices)
