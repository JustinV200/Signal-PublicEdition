"""The Duo lockout's edges: a tab that goes to Duo mid-action, and popups Duo opens."""

import pytest
from support.browser_helpers import ALLOWED_HOST, ref_for
from support.fake_duo import DUO_ORIGIN, FakeClock, start_with_fake_duo
from support.fakes import ApprovesAfterNavigating

from browser_tool.actions import (
    ActionError,
    answer_dialog,
    click,
    click_at,
    drag,
    find,
    hover,
    navigate,
    press_key,
    reload,
    screenshot,
    scroll,
    snapshot,
    type_text,
    upload_file,
    wait_for,
)
from browser_tool.duo import DUO_LOCKOUT_MESSAGE


@pytest.mark.asyncio
async def test_an_approved_key_is_refused_if_the_tab_went_to_duo_meanwhile(
    make_ctx, fixture_server
):
    ctx = await make_ctx()
    page = await start_with_fake_duo(ctx, FakeClock())
    await navigate(ctx, fixture_server.url(ALLOWED_HOST, "/plain.html"))
    ctx.confirmer = ApprovesAfterNavigating(page, f"{DUO_ORIGIN}/prompt")

    with pytest.raises(ActionError) as refusal:
        await press_key(ctx, "Delete")  # the Delete key asks the owner

    assert str(refusal.value) == DUO_LOCKOUT_MESSAGE
    assert len(ctx.confirmer.requests) == 1  # asked and approved; the re-check refused


@pytest.mark.asyncio
async def test_an_approved_click_is_refused_if_the_tab_went_to_duo_meanwhile(
    make_ctx, fixture_server
):
    ctx = await make_ctx()
    page = await start_with_fake_duo(ctx, FakeClock())
    await navigate(ctx, fixture_server.url(ALLOWED_HOST, "/shop.html"))
    buy_ref = ref_for(await snapshot(ctx), 'button "Buy now for $42"')
    ctx.confirmer = ApprovesAfterNavigating(page, f"{DUO_ORIGIN}/prompt")

    with pytest.raises(ActionError) as refusal:
        await click(ctx, buy_ref)

    assert str(refusal.value) == DUO_LOCKOUT_MESSAGE
    assert len(ctx.confirmer.requests) == 1


@pytest.mark.asyncio
async def test_a_popup_opened_by_a_duo_tab_is_locked_while_it_has_no_host(make_ctx, fixture_server):
    ctx = await make_ctx()
    page = await start_with_fake_duo(ctx, FakeClock())
    await page.goto(f"{DUO_ORIGIN}/prompt")
    async with page.expect_popup() as popup_info:
        await page.evaluate("window.open('about:blank')")
    popup = await popup_info.value
    await ctx.session.select_page(ctx.session.pages().index(popup))

    with pytest.raises(ActionError) as refusal:
        await press_key(ctx, "Tab")
    assert str(refusal.value) == DUO_LOCKOUT_MESSAGE

    await navigate(ctx, fixture_server.url(ALLOWED_HOST, "/plain.html"))
    assert "pressed Tab" in await press_key(ctx, "Tab")


DUO_TAB_ROWS = {
    "find": lambda ctx: find(ctx, "push"),
    "wait_for": lambda ctx: wait_for(ctx, text="push"),
    "double_click": lambda ctx: click(ctx, "e1", double=True),
    "click_at": lambda ctx: click_at(ctx, 10, 10),
    "drag": lambda ctx: drag(ctx, "e1", "e2"),
    "hover": lambda ctx: hover(ctx, "e1"),
    "scroll": lambda ctx: scroll(ctx),
    "type_text_slowly": lambda ctx: type_text(ctx, "e1", "x", append=True, slowly=True),
    "reload": reload,  # reloading the prompt would send a new push
    "answer_dialog": lambda ctx: answer_dialog(ctx, False),
    "upload_file": lambda ctx: upload_file(ctx, "e1", "C:/nowhere.txt"),
    "screenshot_element": lambda ctx: screenshot(ctx, "e1"),
}


@pytest.mark.asyncio
@pytest.mark.parametrize("tool", DUO_TAB_ROWS.values(), ids=DUO_TAB_ROWS.keys())
async def test_tools_refuse_a_duo_tab_first(make_ctx, tool):
    ctx = await make_ctx()
    page = await start_with_fake_duo(ctx, FakeClock())
    await page.goto(f"{DUO_ORIGIN}/prompt")  # also off the allowlist: Duo is checked first

    with pytest.raises(ActionError) as refusal:
        await tool(ctx)
    assert str(refusal.value) == DUO_LOCKOUT_MESSAGE
