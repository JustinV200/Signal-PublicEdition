"""Tests for build_server through an in-process MCP client (`mcp.Client(server)`).

The tool list itself is checked by the real stdio round trip in test_launch.py;
this covers how a tool's ToolError reaches the model over the wire.
"""

import pytest
from mcp import Client

from audiohub.mcp import build_server

pytestmark = pytest.mark.asyncio


async def test_bad_argument_comes_back_as_an_error_result(notify_tool, music_tools, music) -> None:
    async with Client(build_server(notify_tool, music_tools)) as client:
        result = await client.call_tool("music_set_volume", {"percent": 101})
    assert result.is_error
    assert "between 0 and 100" in result.content[0].text
    assert music.calls == []
