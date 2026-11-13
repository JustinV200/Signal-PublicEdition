"""The signed-out note and the login-loop refusal, on headless Edge with the fake vault."""

import pytest
from support.browser_helpers import ALLOWED_HOST, ref_for

from browser_tool.actions import ActionError, click, fill_login, navigate, snapshot
from browser_tool.config import DuoSettings

SITE_NAME = "Demo login"


@pytest.mark.asyncio
async def test_a_password_page_gets_the_note_and_a_third_fill_is_refused(make_ctx, fixture_server):
    # answer=True: this fixture form has extra fields, so its Sign in asks as a send.
    ctx = await make_ctx(answer=True, duo=DuoSettings(site_names={ALLOWED_HOST: SITE_NAME}))
    login_url = fixture_server.url(ALLOWED_HOST, "/login.html")

    # A visible password field marks a login page; the owner's name is shown.
    first = await navigate(ctx, login_url)
    assert f"signed out: this is {SITE_NAME}'s login page" in first
    submit = ref_for(await snapshot(ctx), 'button "Sign in"')
    assert await fill_login(ctx, "demo", False) == "ok"
    # Its submit lands on a page with no password field: no note.
    assert "signed out" not in await click(ctx, submit)

    # Asked again: one retry is allowed, then the site's fills are used up.
    assert "login loop" not in await navigate(ctx, login_url)
    assert await fill_login(ctx, "demo", False) == "ok"
    assert "login loop" in await navigate(ctx, login_url)
    with pytest.raises(ActionError, match="login loop"):
        await fill_login(ctx, "demo", False)
    assert len(ctx.filler.filled_pages) == 2
