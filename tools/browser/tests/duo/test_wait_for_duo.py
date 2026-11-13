"""wait_for_duo and the voice ping line, on headless Edge with fake Duo and a fake hub.

The hub is a local asyncio server (tests/duo/conftest.py) answering with
`hub_reply`, or a missing token file; the real hub is never reached. Approval is
simulated by the test moving the tab off Duo, as Duo's redirect back would.
"""

import asyncio

import pytest
from support.browser_helpers import ALLOWED_HOST
from support.fake_duo import (
    DUO_ORIGIN,
    HUB_ASLEEP_REPLY,
    HUB_OK_REPLY,
    NOTICE_MARK,
    FakeClock,
    follow_login_to_duo,
    start_with_fake_duo,
)

from browser_tool.actions import ActionError, click, list_tabs, navigate, wait_for_duo
from browser_tool.config import DuoSettings
from browser_tool.duo import DUO_LOCKOUT_MESSAGE
from browser_tool.server import ToolRunner

ADD_DUO_IFRAME = (
    "document.body.append(Object.assign(document.createElement('iframe'), "
    f"{{id: 'duo', src: '{DUO_ORIGIN}/frame'}}))"
)
# Long enough for wait_for_duo to read the ping and start waiting.
WAIT_STARTED_S = 0.5


async def _site_then_duo(ctx, server, clock, duo_path="/prompt"):
    """Open the site, then have its own page send the tab to fake Duo."""
    page = await start_with_fake_duo(ctx, clock)
    await navigate(ctx, server.url(ALLOWED_HOST, "/plain.html"))
    await follow_login_to_duo(page, duo_path)
    return page


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("hub_reply", "hub_rings_through", "has_hub", "prompts", "expected"),
    [
        (HUB_OK_REPLY, False, True, 1, "voice ping: spoken"),
        # The owner is asleep, but the Duo heads-up rings through.
        (HUB_ASLEEP_REPLY, True, True, 1, "voice ping: spoken"),
        # A hub that doesn't honour ring_through still drops it.
        (HUB_ASLEEP_REPLY, False, True, 1, "voice ping dropped: the owner is asleep"),
        (HUB_OK_REPLY, False, False, 1, "voice hub not running"),
        # A second prompt inside min_heads_up_interval_s isn't spoken.
        (HUB_OK_REPLY, False, True, 2, "voice ping skipped: one was sent under 60 s ago"),
    ],
    ids=["spoken", "asleep-rings-through", "dropped", "no-hub", "rate-limited"],
)
async def test_the_notice_says_how_the_voice_ping_went(
    make_ctx, fixture_server, fake_hub, has_hub, prompts, expected
):
    settings, _ = fake_hub
    clock = FakeClock()
    ctx = await make_ctx(duo=settings if has_hub else DuoSettings())
    page = await start_with_fake_duo(ctx, clock)
    runner = ToolRunner(ctx)
    await navigate(ctx, fixture_server.url(ALLOWED_HOST, "/duo_iframe.html"))
    await page.wait_for_load_state("load")
    for _ in range(prompts - 1):
        await ctx.session.duo.take_notices()
        async with page.expect_event("framedetached"):
            await page.evaluate("document.getElementById('duo').remove()")
        clock.now += ctx.settings.duo.same_prompt_window_s + 1
        async with page.expect_event("framenavigated", lambda f: f.url.startswith(DUO_ORIGIN)):
            await page.evaluate(ADD_DUO_IFRAME)

    result = await runner.run("tabs", list_tabs)
    assert result.count(NOTICE_MARK) == 1
    assert result.endswith(f"\n{expected}")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("landing", "expected_note"),
    [
        ("/plain.html", None),
        # Duo sent the tab back to a login page: the signed-out note comes too.
        ("/login.html", f"signed out: this is {ALLOWED_HOST}'s login page"),
    ],
    ids=["site", "login-page"],
)
async def test_wait_for_duo_reports_where_the_approved_tab_landed(
    make_ctx, fixture_server, fake_hub, landing, expected_note
):
    settings, _ = fake_hub
    ctx = await make_ctx(duo=settings)
    page = await start_with_fake_duo(ctx, FakeClock())
    await navigate(ctx, fixture_server.url(ALLOWED_HOST, "/plain.html"))
    assert await wait_for_duo(ctx, 5) == "no Duo prompt on this tab"
    await follow_login_to_duo(page, "/prompt")

    waiting = asyncio.create_task(wait_for_duo(ctx, 10))
    await asyncio.sleep(WAIT_STARTED_S)
    await page.goto(fixture_server.url(ALLOWED_HOST, landing))
    result = await waiting

    assert result.startswith(f"Duo approved; now at http://{ALLOWED_HOST}:")
    assert landing in result
    assert (expected_note in result) if expected_note else ("signed out" not in result)


@pytest.mark.asyncio
async def test_wait_for_duo_times_out_without_touching_duo_and_the_lockout_holds(
    make_ctx, fixture_server, fake_hub
):
    settings, _ = fake_hub
    ctx = await make_ctx(duo=settings)
    page = await _site_then_duo(ctx, fixture_server, FakeClock(), "/counted")

    result = await wait_for_duo(ctx, 1)

    assert result.startswith("the Duo prompt is still waiting after 1 s (voice ping: spoken)")
    assert await page.evaluate("window.inputEvents") == 0
    with pytest.raises(ActionError) as refusal:
        await click(ctx, "e1")
    assert str(refusal.value) == DUO_LOCKOUT_MESSAGE


@pytest.mark.asyncio
@pytest.mark.parametrize("hub_reply", [HUB_ASLEEP_REPLY])
@pytest.mark.parametrize(
    ("wait_anyway", "expected_start"),
    [
        (False, "voice ping dropped: the owner is asleep; the push is still on the phone"),
        (
            True,
            "the Duo prompt is still waiting after 1 s (voice ping dropped: the owner is asleep)",
        ),
    ],
    ids=["returns-at-once", "wait-anyway"],
)
async def test_a_dropped_ping_returns_at_once_unless_wait_anyway(
    make_ctx, fixture_server, fake_hub, wait_anyway, expected_start
):
    settings, _ = fake_hub
    ctx = await make_ctx(duo=settings)
    await _site_then_duo(ctx, fixture_server, FakeClock())

    assert (await wait_for_duo(ctx, 1, wait_anyway)).startswith(expected_start)
