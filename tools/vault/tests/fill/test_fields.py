"""Field finding: the username is chosen by the vault, never by the model."""

import pytest

from vault.fill.fields import find_login_fields


async def _id_of(handle) -> str | None:
    return None if handle is None else await handle.get_attribute("id")


@pytest.mark.asyncio
async def test_username_is_the_last_visible_text_input_before_the_password(page):
    await page.set_content(
        '<input id="search"><form><input id="hidden" style="display:none">'
        '<input id="user"><input id="pass" type="password"><input id="after"></form>'
    )

    fields = await find_login_fields(page)

    assert await _id_of(fields.password) == "pass"
    assert await _id_of(fields.username) == "user"


@pytest.mark.asyncio
async def test_password_only_forms_have_no_username_field(page):
    await page.set_content('<form><input id="pass" type="password"></form>')

    fields = await find_login_fields(page)

    assert fields.username is None


REGISTER_NEXT_TO_LOGIN = (
    '<form><input id="user"><input id="pass" type="password"></form>'
    '<form><input id="email"><input id="new" type="password" autocomplete="new-password">'
    '<input id="new2" type="password" autocomplete="new-password"></form>'
)
# Filling here would put the saved password in "current password".
CHANGE_PASSWORD_FORM = (
    '<form><input id="cur" type="password" autocomplete="current-password">'
    '<input id="new" type="password" autocomplete="new-password">'
    '<input id="new2" type="password" autocomplete="new-password"></form>'
)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("html", "expected"),
    [(REGISTER_NEXT_TO_LOGIN, ("pass", "user")), (CHANGE_PASSWORD_FORM, None)],
)
async def test_new_password_fields_only_block_their_own_form(page, html, expected):
    await page.set_content(html)

    fields = await find_login_fields(page)

    if expected is None:
        assert fields is None
    else:
        assert (await _id_of(fields.password), await _id_of(fields.username)) == expected
