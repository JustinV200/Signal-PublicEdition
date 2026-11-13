"""Real Edge launches: password saving is off, and the session relaunches after close."""

import json

import pytest

PREFS_PAGE = "edge://prefs-internals"


def pref_value(prefs: dict, dotted_name: str):
    node = prefs
    for part in dotted_name.split("."):
        node = node[part]
    return node["value"]


@pytest.mark.asyncio
async def test_edge_password_manager_is_disabled_in_the_profile(make_ctx):
    ctx = await make_ctx()
    page = await ctx.session.current_page()
    # edge:// pages bypass routing; this reads Edge's effective prefs.
    await page.goto(PREFS_PAGE)
    prefs = json.loads(await page.locator("body").inner_text())
    assert pref_value(prefs, "credentials_enable_service") is False
    assert pref_value(prefs, "credentials_enable_autofill_passwords") is False
    assert pref_value(prefs, "autofill.profile_enabled") is False


@pytest.mark.asyncio
async def test_session_is_lazy_and_relaunches_after_close(make_ctx):
    ctx = await make_ctx()
    assert not ctx.session.is_started
    assert ctx.session.pages() == []
    await ctx.session.current_page()
    assert ctx.session.is_started
    await ctx.session.close()
    assert not ctx.session.is_started
    page = await ctx.session.current_page()
    assert not page.is_closed()
