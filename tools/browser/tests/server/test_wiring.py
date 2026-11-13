"""Backend selection: the docker server has no credential tools and never imports the vault."""

import sys
from dataclasses import replace

import pytest
from support.browser_helpers import headless_settings
from support.fakes import FakeConfirmer

from browser_tool.config import GateSettings
from browser_tool.server import BACKEND_DOCKER, build_context, build_server

DOCKER_TOOLS = {
    "navigate", "snapshot", "click", "type_text", "select_option", "press_key", "back",
    "tabs", "switch_tab", "screenshot", "wait_for_duo", "click_at", "drag", "hover", "scroll",
    "forward", "reload", "new_tab", "close_tab", "find", "wait_for", "answer_dialog",
}  # fmt: skip


@pytest.mark.asyncio
async def test_docker_backend_has_no_credential_tools_and_never_imports_the_vault(
    tmp_path, monkeypatch
):
    monkeypatch.delitem(sys.modules, "vault", raising=False)
    ctx = build_context(BACKEND_DOCKER, headless_settings(tmp_path), FakeConfirmer())
    server = build_server(ctx, is_docker=True)
    assert {tool.name for tool in await server.list_tools()} == DOCKER_TOOLS
    assert not ctx.uploads_allowed  # upload_file refuses even if called directly
    assert not ctx.downloads_readable  # and so does read_download
    # Every filler call the actions and the result scrub make.
    assert ctx.filler.scrub(None, "text") == "text"
    assert await ctx.filler.has_filled_fields(None) is False
    assert "vault" not in sys.modules


def test_docker_backend_refuses_allow_secret_fields(tmp_path):
    settings = headless_settings(tmp_path)
    settings = replace(settings, gates=GateSettings(allow_secret_fields=True))
    with pytest.raises(ValueError, match="allow_secret_fields"):
        build_context(BACKEND_DOCKER, settings, FakeConfirmer())
