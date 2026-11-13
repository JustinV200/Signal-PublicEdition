"""type_text refusal and the owner-confirmation gate, on headless Edge with a fake Confirmer.

Which actions ask under each [gates] always_confirm setting is in test_always_confirm.py.
"""

import pytest
from support.browser_helpers import ALLOWED_HOST, OTHER_HOST, ref_for
from support.fakes import ApprovesAfterNavigating

from browser_tool.actions import (
    PASSWORD_FIELD_REFUSAL,
    TAB_MOVED_REFUSAL,
    UNTRUSTED_OPEN,
    ActionError,
    click,
    click_at,
    navigate,
    press_key,
    scroll,
    snapshot,
    type_text,
)
from browser_tool.config import GateSettings


async def _open(ctx, server, page_name: str) -> str:
    await navigate(ctx, server.url(ALLOWED_HOST, page_name))
    return await snapshot(ctx)


async def _status(ctx) -> str:
    page = await ctx.session.current_page()
    return await page.locator("#status").inner_text()


@pytest.mark.asyncio
@pytest.mark.parametrize("allow_secret_fields", [False, True])
async def test_type_text_in_password_and_otp_fields_follows_config(
    make_ctx, fixture_server, allow_secret_fields
):
    gates = GateSettings(allow_secret_fields=allow_secret_fields)
    ctx = await make_ctx(gates=gates)
    text = await _open(ctx, fixture_server, "/login.html")
    page = await ctx.session.current_page()
    for label, field_id in (('textbox "Password"', "password"), ('textbox "Code"', "otp")):
        ref = ref_for(text, label)
        if not allow_secret_fields:
            with pytest.raises(ActionError) as refusal:
                await type_text(ctx, ref, "model-typed-secret")
            assert str(refusal.value) == PASSWORD_FIELD_REFUSAL
            assert "model-typed-secret" not in await page.locator(f"#{field_id}").input_value()
            continue
        result = await type_text(ctx, ref, "model-typed-secret")
        assert await page.locator(f"#{field_id}").input_value() == "model-typed-secret"
        # Allowed typing still never shows the value: not in the result or a snapshot.
        assert "model-typed-secret" not in result + await snapshot(ctx)


@pytest.mark.asyncio
async def test_type_text_appends_and_types_slowly_without_pressing_enter(make_ctx, fixture_server):
    ctx = await make_ctx()
    text = await _open(ctx, fixture_server, "/confirm.html")
    field_ref = ref_for(text, 'textbox "Say something"')  # Enter would submit its form
    page = await ctx.session.current_page()

    await type_text(ctx, field_ref, "ab")
    assert "added 4 characters" in await type_text(
        ctx, field_ref, "c\td\n", append=True, slowly=True
    )
    await type_text(ctx, field_ref, "z", append=True)

    field = page.get_by_label("Say something", exact=True)
    assert await field.input_value() == "abc\tdz"  # the tab typed as text, the line break dropped
    assert await _status(ctx) == "idle"  # no Enter: the form was not submitted
    assert await field.evaluate("(el) => el === document.activeElement")  # no Tab moved focus

    message_ref = ref_for(text, 'textbox "Online text"')
    await type_text(ctx, message_ref, "line 1\r\nline 2", slowly=True)
    message = page.get_by_label("Online text", exact=True)
    assert await message.input_value() == "line 1\nline 2"  # a textarea keeps its line break
    assert await _status(ctx) == "idle"


@pytest.mark.asyncio
async def test_a_double_click_fires_dblclick(make_ctx, fixture_server):
    ctx = await make_ctx()
    text = await _open(ctx, fixture_server, "/confirm.html")
    # Two halves with a re-check between them still make one double click.
    assert "double-clicked" in await click(ctx, ref_for(text, 'button "Open"'), double=True)
    assert await _status(ctx) == "opened"


@pytest.mark.asyncio
async def test_typing_slowly_stops_when_the_page_moves_focus(make_ctx, fixture_server):
    ctx = await make_ctx()
    text = await _open(ctx, fixture_server, "/confirm.html")

    with pytest.raises(ActionError, match="could not put the cursor"):
        await type_text(ctx, ref_for(text, 'textbox "Jumpy"'), "a b", slowly=True)

    assert await _status(ctx) == "idle"  # the space never pressed the Jump button


@pytest.mark.asyncio
async def test_an_approved_click_at_is_refused_if_another_element_is_there_now(
    make_ctx, fixture_server
):
    ctx = await make_ctx()
    await _open(ctx, fixture_server, "/shop.html")
    page = await ctx.session.current_page()
    box = await page.locator("#buy").bounding_box()
    # Approved, but meanwhile the same site put other content under the point.
    ctx.confirmer = ApprovesAfterNavigating(page, fixture_server.url(ALLOWED_HOST, "/shop.html"))

    with pytest.raises(ActionError, match="the page changed under that point"):
        await click_at(ctx, box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)

    assert len(ctx.confirmer.requests) == 1
    assert await _status(ctx) == "idle"


@pytest.mark.asyncio
async def test_scroll_reports_the_view_and_more_content_loading(make_ctx, fixture_server):
    ctx = await make_ctx()
    await navigate(ctx, fixture_server.url(ALLOWED_HOST, "/scroll.html"))

    assert "scrolled down: showing 720-1440 of" in await scroll(ctx)
    assert "it grew from" in await scroll(ctx, amount=10)  # the end: the feed loads more
    assert "at the start" in await scroll(ctx, direction="up", amount=10)


@pytest.mark.asyncio
async def test_purchase_click_waits_for_the_owner(make_ctx, fixture_server):
    ctx = await make_ctx(answer=False)
    text = await _open(ctx, fixture_server, "/shop.html")
    assert "clicked" in await click(ctx, ref_for(text, 'button "Show details"'))
    assert ctx.confirmer.requests == []  # ordinary clicks are not gated

    buy_ref = ref_for(text, 'button "Buy now for $42"')
    with pytest.raises(ActionError, match="not done: the owner did not approve"):
        await click(ctx, buy_ref)
    assert await _status(ctx) == "info shown"
    [request] = ctx.confirmer.requests
    assert "Buy now for $42" in request.action
    assert request.origin == f"http://{ALLOWED_HOST}:{fixture_server.port}"

    ctx.confirmer.answer = True
    assert f"clicked {UNTRUSTED_OPEN}button" in await click(ctx, buy_ref)
    assert await _status(ctx) == "bought"


@pytest.mark.asyncio
async def test_an_approved_key_is_refused_if_the_tab_moved_to_another_allowed_site(
    make_ctx, fixture_server
):
    ctx = await make_ctx(allow=(ALLOWED_HOST, OTHER_HOST))
    await navigate(ctx, fixture_server.url(ALLOWED_HOST, "/plain.html"))
    page = await ctx.session.current_page()
    ctx.confirmer = ApprovesAfterNavigating(page, fixture_server.url(OTHER_HOST, "/plain.html"))

    with pytest.raises(ActionError, match=TAB_MOVED_REFUSAL) as refusal:
        await press_key(ctx, "Delete")  # the Delete key asks the owner

    assert f"to http://{OTHER_HOST}:{fixture_server.port}" in str(refusal.value)
    assert len(ctx.confirmer.requests) == 1  # asked and approved; the re-check refused


@pytest.mark.asyncio
async def test_an_approved_click_is_refused_if_the_tab_moved_to_another_allowed_site(
    make_ctx, fixture_server
):
    ctx = await make_ctx(allow=(ALLOWED_HOST, OTHER_HOST))
    buy_ref = ref_for(await _open(ctx, fixture_server, "/shop.html"), 'button "Buy now for $42"')
    page = await ctx.session.current_page()
    ctx.confirmer = ApprovesAfterNavigating(page, fixture_server.url(OTHER_HOST, "/shop.html"))

    with pytest.raises(ActionError, match=TAB_MOVED_REFUSAL):
        await click(ctx, buy_ref)

    assert await _status(ctx) == "idle"  # nothing was bought on the other site


@pytest.mark.asyncio
async def test_a_click_that_closes_its_tab_is_reported_as_done(make_ctx, fixture_server):
    ctx = await make_ctx()
    await navigate(ctx, fixture_server.url(ALLOWED_HOST, "/plain.html"))
    page = await ctx.session.current_page()
    async with page.expect_popup() as popup_info:
        await page.evaluate(f"window.open('{fixture_server.url(ALLOWED_HOST, '/closer.html')}')")
    popup = await popup_info.value
    await ctx.session.select_page(ctx.session.pages().index(popup))

    result = await click(ctx, ref_for(await snapshot(ctx), 'button "Done"'))

    assert "the tab closed" in result
    assert popup.is_closed()
