"""Allowlist/denylist enforcement on headless Edge, including redirects and subresources."""

import pytest
from support.browser_helpers import ALLOWED_HOST, BLOCKED_HOST, OTHER_HOST

from browser_tool.actions import (
    ActionError,
    back,
    close_tab,
    forward,
    list_tabs,
    navigate,
    new_tab,
    reload,
)


@pytest.mark.asyncio
async def test_allowlist_refuses_other_hosts_and_follows_allowed_redirects(
    make_ctx, fixture_server
):
    ctx = await make_ctx(allow=(ALLOWED_HOST, OTHER_HOST))
    result = await navigate(ctx, fixture_server.url(ALLOWED_HOST, f"/redirect?to={OTHER_HOST}"))
    assert f"http://{OTHER_HOST}:{fixture_server.port}/plain.html" in result
    with pytest.raises(ActionError, match="blocked.*not_allowlisted"):
        await navigate(ctx, fixture_server.url(BLOCKED_HOST, "/plain.html"))
    assert BLOCKED_HOST not in fixture_server.hosts_hit()


@pytest.mark.asyncio
async def test_redirect_to_non_allowlisted_host_is_blocked_before_it_is_sent(
    make_ctx, fixture_server
):
    ctx = await make_ctx(allow=(ALLOWED_HOST,))
    with pytest.raises(ActionError, match=f"blocked.*{BLOCKED_HOST}"):
        await navigate(ctx, fixture_server.url(ALLOWED_HOST, f"/redirect?to={BLOCKED_HOST}"))
    assert ALLOWED_HOST in fixture_server.hosts_hit()
    assert BLOCKED_HOST not in fixture_server.hosts_hit()


@pytest.mark.asyncio
async def test_denylist_blocks_direct_and_redirected_navigation_in_allow_all_mode(
    make_ctx, fixture_server
):
    ctx = await make_ctx(allow_all=True, deny=(BLOCKED_HOST,))
    assert "navigated to" in await navigate(ctx, fixture_server.url(OTHER_HOST, "/plain.html"))
    with pytest.raises(ActionError, match="denylisted"):
        await navigate(ctx, fixture_server.url(BLOCKED_HOST, "/plain.html"))
    with pytest.raises(ActionError, match="blocked"):
        await navigate(ctx, fixture_server.url(OTHER_HOST, f"/redirect?to={BLOCKED_HOST}"))
    assert BLOCKED_HOST not in fixture_server.hosts_hit()


@pytest.mark.asyncio
async def test_subresource_from_blocked_host_is_never_requested(make_ctx, fixture_server):
    ctx = await make_ctx(allow=(ALLOWED_HOST,))
    await navigate(ctx, fixture_server.url(ALLOWED_HOST, "/subresource.html"))
    page = await ctx.session.current_page()
    await page.wait_for_load_state("load")
    assert f"{ALLOWED_HOST}:{fixture_server.port}/pixel.png" in fixture_server.hits
    assert BLOCKED_HOST not in fixture_server.hosts_hit()


@pytest.mark.asyncio
async def test_non_web_and_credential_urls_are_refused_before_launch(make_ctx, fixture_server):
    ctx = await make_ctx()
    for url in ("file:///C:/Windows/win.ini", "javascript:alert(1)", "data:text/html,hi"):
        with pytest.raises(ActionError, match="only http and https"):
            await navigate(ctx, url)
    with pytest.raises(ActionError, match="embedded credentials"):
        await navigate(ctx, f"http://{ALLOWED_HOST}@{BLOCKED_HOST}:{fixture_server.port}/")
    assert not ctx.session.is_started


@pytest.mark.asyncio
async def test_history_and_tabs(make_ctx, fixture_server):
    ctx = await make_ctx()
    await navigate(ctx, fixture_server.url(ALLOWED_HOST, "/plain.html"))
    await navigate(ctx, fixture_server.url(ALLOWED_HOST, "/shop.html"))
    assert "/plain.html" in await back(ctx)
    assert "/shop.html" in await forward(ctx)
    assert "no next page" in await forward(ctx)
    page = await ctx.session.current_page()
    await page.evaluate("location.hash = 'details'")
    assert "went back to" in await back(ctx)  # a hash-only step is a step (B8)

    with pytest.raises(ActionError, match="not allowed"):
        await new_tab(ctx, fixture_server.url(BLOCKED_HOST, "/plain.html"))
    assert len(ctx.session.pages()) == 1  # refused before a tab opened
    assert (await new_tab(ctx, fixture_server.url(ALLOWED_HOST, "/plain.html"))).startswith(
        "opened tab 1; navigated to"
    )
    tabs = await list_tabs(ctx)
    assert "[1] (current)" in tabs
    assert "title: <untrusted_page_content>Plain fixture</untrusted_page_content>" in tabs
    assert "closed tab 1; current tab is 0" in await close_tab(ctx, 1)
    with pytest.raises(ActionError, match="only tab"):
        await close_tab(ctx, 0)


@pytest.mark.asyncio
async def test_reload_and_forward_onto_a_form_post_ask_as_a_send(make_ctx, fixture_server):
    ctx = await make_ctx()
    await navigate(ctx, fixture_server.url(ALLOWED_HOST, "/post_form.html"))
    assert "reloaded" in await reload(ctx)  # a GET page reloads without asking
    page = await ctx.session.current_page()
    async with page.expect_navigation():
        await page.click("button")  # the form POSTs to /posted
    assert len(fixture_server.posts) == 1

    with pytest.raises(ActionError, match="not done"):
        await reload(ctx)
    assert "/post_form.html" in await back(ctx)
    with pytest.raises(ActionError, match="not done"):
        await forward(ctx)
    assert len(fixture_server.posts) == 1  # nothing was sent again
    assert page.url.endswith("/post_form.html")  # and the tab stayed put
    assert len(ctx.confirmer.requests) == 2

    ctx.confirmer.answer = True
    assert "went forward to" in await forward(ctx)
    assert len(fixture_server.posts) == 2

    # An iframe's form: back moves only the iframe, and forward would re-send it.
    ctx.confirmer.answer = False
    await navigate(ctx, fixture_server.url(ALLOWED_HOST, "/post_frame.html"))
    frame = page.frames[1]
    async with frame.expect_navigation():
        await frame.click("button")
    assert "went back to" in await back(ctx)  # an iframe-only step is a move
    with pytest.raises(ActionError, match="not done"):
        await forward(ctx)
    assert len(fixture_server.posts) == 3  # the iframe's POST was not sent again
