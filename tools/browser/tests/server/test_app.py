"""End-to-end through MCPServer.call_tool: fill_login never reveals the secret."""

import logging

import pytest
from mcp.server.mcpserver.exceptions import ToolError
from support.browser_helpers import ALLOWED_HOST, ref_for
from support.fakes import SCRUBBED, SECRET_PASSWORD, SECRET_USERNAME

from browser_tool.credentials import MissingVaultFiller
from browser_tool.server import build_server

EXPECTED_TOOLS = {
    "navigate", "snapshot", "click", "type_text", "select_option", "press_key", "back",
    "tabs", "switch_tab", "screenshot", "wait_for_duo", "click_at", "drag", "hover", "scroll",
    "forward", "reload", "new_tab", "close_tab", "list_credentials", "fill_login",
    "find", "wait_for", "answer_dialog", "upload_file", "read_download",
}  # fmt: skip


async def call(server, name: str, arguments: dict | None = None) -> tuple[str, bool]:
    """Call a tool; return (text, is_error)."""
    try:
        result = await server.call_tool(name, arguments or {})
    except ToolError as error:
        return str(error), True
    return "".join(block.text for block in result.content), bool(result.is_error)


@pytest.mark.asyncio
async def test_server_exposes_exactly_the_designed_tools(make_ctx):
    server = build_server(await make_ctx())
    assert {tool.name for tool in await server.list_tools()} == EXPECTED_TOOLS


@pytest.mark.asyncio
async def test_fill_login_returns_only_ok_or_error_never_the_secret(
    make_ctx, fixture_server, caplog
):
    caplog.set_level(logging.DEBUG)
    ctx = await make_ctx()
    server = build_server(ctx)
    await call(server, "navigate", {"url": fixture_server.url(ALLOWED_HOST, "/login.html")})
    assert await call(server, "fill_login", {"credential_id": "demo"}) == ("ok", False)
    page = await ctx.session.current_page()
    assert await page.locator("#password").input_value() == SECRET_PASSWORD  # it did fill

    ctx.filler.error = RuntimeError(f"decrypt failed for {SECRET_PASSWORD}")
    assert await call(server, "fill_login", {"credential_id": "demo"}) == ("failed: error", False)
    assert SECRET_PASSWORD not in caplog.text and SECRET_USERNAME not in caplog.text


@pytest.mark.asyncio
async def test_every_result_passes_through_vault_scrub(make_ctx, fixture_server):
    server = build_server(await make_ctx())
    await call(server, "navigate", {"url": fixture_server.url(ALLOWED_HOST, "/login.html")})
    snapshot_text, _ = await call(server, "snapshot")
    username_ref = ref_for(snapshot_text, 'textbox "Username"')
    await call(server, "type_text", {"ref": username_ref, "text": SECRET_USERNAME})
    text, is_error = await call(server, "snapshot")
    assert not is_error
    assert SECRET_USERNAME not in text and SCRUBBED in text


@pytest.mark.asyncio
async def test_credential_tools_report_missing_vault(make_ctx, fixture_server):
    server = build_server(await make_ctx(filler=MissingVaultFiller()))
    assert await call(server, "list_credentials") == ("vault not installed", False)
    await call(server, "navigate", {"url": fixture_server.url(ALLOWED_HOST, "/login.html")})
    result = await call(server, "fill_login", {"credential_id": "demo"})
    assert result == ("vault not installed", False)
