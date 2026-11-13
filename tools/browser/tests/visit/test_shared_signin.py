"""The checker shares the desktop browser's sign-in through the saved cookies, on headless Edge.

The desktop session (CookieMode.OWN) saves its cookies on a clean close; a visit
(CookieMode.BORROW, its own profile) starts with the ones its policy allows, so
a Moodle target that needs the stand-in session cookie is read without a login
fill. The desktop gets its session cookie back on its next launch too.
"""

from dataclasses import replace

import pytest
from support.browser_helpers import BLOCKED_HOST, headless_settings
from support.fakes import FakeConfirmer, FakeLoginFiller
from support.visit_support import (
    CAS,
    MOODLE,
    MOODLE_ALLOW,
    MOODLE_VISIT,
    SESSION_COOKIE,
    SubmittingFiller,
    target,
    visit_context,
)

from browser_tool.actions import ActionContext
from browser_tool.cookie_store import CookieMode
from browser_tool.visit import run_visit


def _desktop(tmp_path) -> ActionContext:
    """A desktop-like session: its own profile, the same cookie file as the visit."""
    settings = headless_settings(tmp_path, (*MOODLE_ALLOW, BLOCKED_HOST))
    browser = replace(settings.browser, profile_dir=str(tmp_path / "desktop-profile"))
    return ActionContext.create(
        replace(settings, browser=browser),
        FakeConfirmer(),
        FakeLoginFiller(),
        cookie_mode=CookieMode.OWN,
    )


async def _session_cookies(ctx: ActionContext) -> set[str]:
    page = await ctx.session.current_page()
    return {cookie["name"] for cookie in await page.context.cookies()}


@pytest.mark.asyncio
async def test_a_visit_borrows_the_desktop_sign_in_and_the_desktop_keeps_it(
    tmp_path, fixture_server
):
    desktop = _desktop(tmp_path)
    page = await desktop.session.current_page()
    await page.context.add_cookies(
        [
            {"name": SESSION_COOKIE, "value": "1", "url": fixture_server.url(MOODLE, "/")},
            # Not on the checker's allowlist: never borrowed.
            {"name": "not-for-checker", "value": "1", "url": fixture_server.url(BLOCKED_HOST, "/")},
        ]
    )
    await desktop.session.close()  # the clean close saves them

    filler = SubmittingFiller()
    ctx, _ = visit_context(tmp_path, MOODLE_ALLOW, MOODLE_VISIT, filler)
    url = fixture_server.url(MOODLE, f"/needs-login?login={CAS}")
    result = await run_visit(ctx, (target("p0", url),), MOODLE_VISIT)

    assert [page.status for page in result.pages] == ["ok"]
    assert filler.calls == []  # signed in already: no CAS login, no Duo

    relaunched = _desktop(tmp_path)
    try:
        assert await _session_cookies(relaunched) == {SESSION_COOKIE, "not-for-checker"}
    finally:
        await relaunched.session.close()
