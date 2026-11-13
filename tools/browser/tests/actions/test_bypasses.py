"""Known gate bypasses from security review, each reproduced on headless Edge.

Every attempt must be refused or held for the owner (the fake Confirmer says no)
and leave the page untouched. The snapshot is read through the ToolRunner like a
real tool result; that it never shows this page's leaked password values is
checked in page/test_reading.py's security test.
"""

import re
from dataclasses import replace

import pytest
from support.browser_helpers import ALLOWED_HOST, ref_for

from browser_tool.actions import (
    ActionError,
    click,
    navigate,
    press_key,
    select_option,
    snapshot,
    type_text,
)
from browser_tool.policy import origin_of
from browser_tool.server import ToolRunner


def label_ref(text: str, index: int) -> str:
    """Ref of the index-th clickable <label> (rendered with [cursor=pointer])."""
    return re.findall(r"- generic \[ref=(\w+)\] \[cursor=pointer\]", text)[index]


async def carriage_return_as_enter(ctx, page, text):
    await press_key(ctx, "\r")


async def enter_in_chat_outside_a_form(ctx, page, text):
    await type_text(ctx, ref_for(text, 'textbox "Chat"'), "hi")
    await press_key(ctx, "Enter")


async def letter_in_password_field(ctx, page, text):
    await page.locator("#password").focus()
    await press_key(ctx, "a")


async def paste_into_a_message_box(ctx, page, text):
    await page.get_by_label("Chat", exact=True).focus()
    await press_key(ctx, "Shift+Insert")  # would type the owner's real clipboard


async def paste_variant_in_password_field(ctx, page, text):
    await page.locator("#password").focus()
    await press_key(ctx, "Control+Shift+V")


async def enter_on_shadow_dom_delete_on_exempt_origin(ctx, page, text):
    exempt = (origin_of(page.url),)
    ctx.settings = replace(
        ctx.settings, gates=replace(ctx.settings.gates, no_confirm_origins=exempt)
    )
    await page.locator("shadow-delete button").focus()
    await press_key(ctx, "Enter")


async def submit_button_tied_by_form_attribute(ctx, page, text):
    await click(ctx, ref_for(text, 'button "Continue"'))


async def select_through_its_label(ctx, page, text):
    await select_option(ctx, label_ref(text, 0), "x1")


async def select_named_delete_through_its_label(ctx, page, text):
    await select_option(ctx, label_ref(text, 1), "yes")  # option "Yes" is harmless


async def label_click_submits_a_form(ctx, page, text):
    await click(ctx, ref_for(text, ": Go ahead"))


async def icon_inside_delete_menuitem(ctx, page, text):
    await click(ctx, ref_for(text, 'img "menu icon"'))


async def icon_inside_clickable_send_div(ctx, page, text):
    await click(ctx, ref_for(text, 'img "send icon"'))


async def toolbar_centred_on_delete_button(ctx, page, text):
    await click(ctx, ref_for(text, 'toolbar "Tools"'))


async def role_button_inside_delete_link(ctx, page, text):
    await click(ctx, ref_for(text, 'button "Go"'))


async def button_inside_delete_project_host(ctx, page, text):
    await click(ctx, ref_for(text, 'button "Run"'))


async def option_that_does_not_exist(ctx, page, text):
    await select_option(ctx, label_ref(text, 0), "x9")


async def arrow_down_on_a_focused_select(ctx, page, text):
    await page.locator("select").first.focus()
    await press_key(ctx, "ArrowDown")


async def select_on_a_non_select(ctx, page, text):
    await select_option(ctx, ref_for(text, 'button "Continue"'), "x1")


BYPASSES = [
    (carriage_return_as_enter, "bad key"),
    (enter_in_chat_outside_a_form, "not done"),
    (letter_in_password_field, "refused"),
    (paste_variant_in_password_field, "refused"),
    (paste_into_a_message_box, "refused: paste"),
    (enter_on_shadow_dom_delete_on_exempt_origin, "not done.*delete"),
    (submit_button_tied_by_form_attribute, "not done.*submits a form"),
    (select_through_its_label, "not done.*Delete account"),
    (select_named_delete_through_its_label, "not done.*Delete data"),
    (label_click_submits_a_form, "not done.*submits a form"),
    (icon_inside_delete_menuitem, "not done.*delete"),
    (icon_inside_clickable_send_div, "not done.*send"),
    (toolbar_centred_on_delete_button, "not done.*delete"),
    (role_button_inside_delete_link, "not done.*delete"),
    (button_inside_delete_project_host, "not done.*delete"),
    (option_that_does_not_exist, "no option"),
    (arrow_down_on_a_focused_select, "not done"),
    (select_on_a_non_select, "not a dropdown"),
]


@pytest.mark.asyncio
@pytest.mark.parametrize(("attempt", "refusal"), BYPASSES, ids=[a.__name__ for a, _ in BYPASSES])
async def test_gate_bypasses_are_closed(make_ctx, fixture_server, attempt, refusal):
    ctx = await make_ctx(answer=False)
    await navigate(ctx, fixture_server.url(ALLOWED_HOST, "/bypass.html"))
    text = await ToolRunner(ctx).run("snapshot", snapshot)
    page = await ctx.session.current_page()

    with pytest.raises(ActionError, match=refusal):
        await attempt(ctx, page, text)
    assert await page.locator("#status").inner_text() == "idle"
    assert await page.locator("#password").input_value() == ""
