"""Which actions wait for the owner under [gates] always_confirm, on headless Edge.

The fake Confirmer always says no, so an action that asks is refused and leaves
the page "idle"; one that doesn't ask runs without any dialog.
"""

import logging
from collections.abc import Awaitable, Callable
from typing import NamedTuple

import pytest
from support.browser_helpers import ALLOWED_HOST, ref_for
from support.fakes import FakeLoginFiller

from browser_tool.actions import (
    ActionError,
    click,
    click_at,
    drag,
    fill_login,
    hover,
    navigate,
    press_key,
    select_option,
    snapshot,
)
from browser_tool.config import GateSettings
from browser_tool.credentials import FillResult

PAGE = "/confirm.html"
# An OAuth consent page path; consent never asks, but purchases, sends and deletes do.
CONSENT_PAGE = "/consent.html"
SRCDOC = "about:srcdoc"


def clicking(label: str, **options):
    """An action that clicks the snapshot element labelled `label` (with click options)."""

    async def act(ctx, page, text):
        await click(ctx, ref_for(text, label), **options)

    return act


def clicking_at(button_name: str, in_frame: bool = False):
    """An action that click_at()s the centre of the button named `button_name`."""

    async def act(ctx, page, text):
        root = page.frame_locator("iframe") if in_frame else page
        button = root.get_by_role("button", name=button_name, exact=True)
        await button.scroll_into_view_if_needed()
        box = await button.bounding_box()
        await click_at(ctx, box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)

    return act


def by_ref(tool, *labels, **options):
    """An action that calls `tool` with the refs of the snapshot elements labelled `labels`."""

    async def act(ctx, page, text):
        await tool(ctx, *(ref_for(text, label) for label in labels), **options)

    return act


def pressing(key: str, focus_label: str | None = None):
    """An action that presses `key`, after focusing the element named `focus_label`."""

    async def act(ctx, page, text):
        if focus_label:
            await page.get_by_label(focus_label, exact=True).focus()
        await press_key(ctx, key)

    return act


def filled(password_label: str, act):
    """`act`, after filling the password field named `password_label` as fill_login would."""

    async def act_filled(ctx, page, text):
        await page.get_by_label(password_label, exact=True).fill("filled-by-the-vault")
        await act(ctx, page, text)

    return act_filled


class Row(NamedTuple):
    """One case: the action, whether it asks, the frame origin its dialog names, its page."""

    name: str
    act: Callable[..., Awaitable[None]]
    asks: bool
    frame_origin: str | None = None
    path: str = PAGE
    refused: str | None = None  # the refusal right before the click; nobody is asked


ROWS = [
    # Only "Save draft" is exempt: Moodle hands work in on "Save changes".
    Row("save_changes_submits_a_form", clicking('button "Save changes"'), True),
    Row("enter_in_a_single_field_form", pressing("Enter", "Say something"), True),
    # Chromium presses a form's default button on Enter from a checkbox or radio.
    Row("enter_on_a_checkbox_in_a_form", pressing("Enter", "My own work"), True),
    Row("ctrl_enter_outside_a_form", pressing("Control+Enter", "Notes"), True),
    Row("enter_in_a_combobox_composer", pressing("Enter", "Message"), True),
    # A combobox textarea is a composer, so its form isn't a search form.
    Row("enter_in_a_combobox_textarea_form", pressing("Enter", "Chat"), True),
    # A submitter's formmethod=post overrides its form's method="get".
    Row("formmethod_post_in_a_get_form", clicking('button "Apply"'), True),
    Row("send_in_a_srcdoc_frame", clicking('button "Send"'), True, SRCDOC),
    # Every pointer path reaches the purchase, send and delete rules.
    Row("double_click_send", clicking('button "Send reply"', double=True), True),
    # The first click turns "Edit" into "Send": the second half must not press it.
    Row(
        "double_click_an_edit_that_becomes_send",
        clicking('button "Edit"', double=True),
        True,
        refused="changed after it was checked",
    ),
    # The first click scrolls "Other" under the point: the second half must not press it.
    Row(
        "double_click_that_scrolls_another_button_under_it",
        clicking('button "Shift"', double=True),
        True,
        refused="the page moved",
    ),
    Row(
        "control_right_click_pay",
        clicking('button "Pay $10"', button="right", modifiers=["Control"]),
        True,
    ),
    Row("click_at_pay", clicking_at("Pay $10"), True),
    # The hover swaps in "Send": click_at judges the point after the mouse is there.
    Row("click_at_a_hover_swap_to_send", clicking_at("Preview"), True),
    Row("click_a_hover_swap_to_send", clicking('button "Preview"'), True),
    Row("click_at_send_in_a_srcdoc_frame", clicking_at("Send", in_frame=True), True, SRCDOC),
    Row("drag_to_trash", by_ref(drag, 'button "Old note"', 'region "Trash"'), True),
    Row(
        "select_several_with_delete",
        by_ref(select_option, 'listbox "Bulk"', value=["Archive", "Delete"]),
        True,
    ),
    Row("pay_on_a_consent_page", clicking('button "Pay $10"'), True, path=CONSENT_PAGE),
    Row("send_on_a_consent_page", clicking('button "Send"'), True, path=CONSENT_PAGE),
    # A sign-in form's submit isn't a send, but its words still count.
    Row("delete_in_a_password_form", clicking('button "Delete account"'), True, path=CONSENT_PAGE),
    # Sign-in is judged on the submitter's own form, hidden decoys and message forms aside.
    Row("form_attr_out_of_a_login_form", clicking('button "OK"'), True, path=CONSENT_PAGE),
    Row("hidden_password_decoy", clicking('button "Save changes"'), True, path=CONSENT_PAGE),
    Row("password_with_a_textarea", clicking('button "Go"'), True, path=CONSENT_PAGE),
    Row("off_page_password", clicking('button "Sign in"'), True, path=CONSENT_PAGE),
    Row("faded_password", clicking('button "Log in"'), True, path=CONSENT_PAGE),
    Row("shadow_dom_editor", clicking('button "Verify"'), True, path=CONSENT_PAGE),
    Row("clip_path_password", clicking('button "Continue →"'), True, path=CONSENT_PAGE),
    Row("overflow_clipped_password", clicking('button "Continue ›"'), True, path=CONSENT_PAGE),
    # Not filled yet: a real sign-in is filled by fill_login right before the submit.
    Row("empty_password_sign_in", clicking('button "Sign in"'), True),
    Row(
        "too_many_fields_for_sign_in",
        filled("Busy password", clicking('button "Sign in →"')),
        True,
        path=CONSENT_PAGE,
    ),
    Row("save_draft_in_a_form", clicking('button "Save draft"'), False),
    # An explicit GET form only loads a page (Moodle's "Add submission").
    Row("submit_in_a_get_form", clicking('button "Add submission"'), False),
    # Approval is only for purchases, sends and deletes: consent and sign-in run.
    Row("allow_on_a_consent_page", clicking('button "Allow"'), False, path=CONSENT_PAGE),
    Row(
        "authorize_on_a_consent_page",
        clicking('button "Authorize MyApp"'),
        False,
        path=CONSENT_PAGE,
    ),
    Row(
        "continue_as_on_a_consent_page",
        clicking('button "Continue as the owner"'),
        False,
        path=CONSENT_PAGE,
    ),
    Row("click_in_a_password_form", filled("Password", clicking('button "Sign in"')), False),
    Row("enter_in_a_password_form", filled("Password", pressing("Enter", "Username")), False),
    Row(
        "next_in_a_login_form",
        filled("Login password", clicking('button "Next"')),
        False,
        path=CONSENT_PAGE,
    ),
    Row("submit_in_a_role_search_form", clicking('button "Go"'), False),
    Row("enter_in_a_search_box_form", pressing("Enter", "Find"), False),
    Row("click_in_a_srcdoc_frame", clicking('button "Next"'), False),
    Row("click_at_next_in_a_srcdoc_frame", clicking_at("Next", in_frame=True), False),
    Row("hover_over_delete", by_ref(hover, 'button "Delete draft"'), False),
    Row(
        "select_several_without_delete",
        by_ref(select_option, 'listbox "Bulk"', value=["Archive"]),
        False,
    ),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("row", ROWS, ids=[row.name for row in ROWS])
async def test_the_default_asks_only_for_the_confirm_list(make_ctx, fixture_server, row):
    ctx = await make_ctx()
    await navigate(ctx, fixture_server.url(ALLOWED_HOST, row.path))
    text = await snapshot(ctx)
    page = await ctx.session.current_page()

    if row.refused:
        with pytest.raises(ActionError, match=row.refused):
            await row.act(ctx, page, text)
        assert await page.locator("#status").inner_text() == "idle"
        assert ctx.confirmer.requests == []
    elif row.asks:
        with pytest.raises(ActionError, match="not done"):
            await row.act(ctx, page, text)
        assert await page.locator("#status").inner_text() == "idle"
        assert [request.frame_origin for request in ctx.confirmer.requests] == [row.frame_origin]
    else:
        await row.act(ctx, page, text)
        assert ctx.confirmer.requests == []


class DenyingVault(FakeLoginFiller):
    """A vault whose own per-fill dialog the owner answers with Deny."""

    def __init__(self):
        super().__init__()
        self.asked_pages = []

    async def fill_login(self, page, credential_id, *, submit=False):
        self.asked_pages.append(page)
        return FillResult(ok=False, reason="denied")


@pytest.mark.asyncio
async def test_an_empty_list_leaves_only_owner_patterns_and_the_vault_asking(
    make_ctx, fixture_server, caplog
):
    vault = DenyingVault()
    gates = GateSettings(always_confirm=(), patterns=(r"\bgo\b",))
    ctx = await make_ctx(gates=gates, filler=vault)
    await navigate(ctx, fixture_server.url(ALLOWED_HOST, PAGE))
    text = await snapshot(ctx)
    page = await ctx.session.current_page()
    caplog.set_level(logging.INFO)

    await click(ctx, ref_for(text, 'button "Pay $10"'))
    await press_key(ctx, "Delete")
    with pytest.raises(ActionError, match="not done"):  # the owner's own patterns still ask
        await click(ctx, ref_for(text, 'button "Go"'))

    assert await page.locator("#status").inner_text() == "paid"
    assert len(ctx.confirmer.requests) == 1  # only "Go"
    assert "auto-allowed click" in caplog.text  # logged instead of asked...
    assert "Pay $10" not in caplog.text  # ...without page text
    assert await fill_login(ctx, "demo", submit=True) == "failed: denied"
    assert vault.asked_pages == [page]
    assert await page.get_by_label("Password", exact=True).input_value() == ""
