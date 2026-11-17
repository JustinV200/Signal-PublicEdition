"""The chamber MCP server: exactly five tools, and DaemonError becomes a tool error."""

import sys
import types

import pytest
from mcp.client import Client

from analysis_chamber.mcp_server import build_server


class FakeError(Exception):
    """Stands in for DaemonError."""


class FakeClient:
    def __init__(self, state_dir):
        pass

    def start(self, question):
        return {"run_id": "r1", "plan": "p"}

    def approve(self, run_id, edits=None, personal=None):
        FakeClient.approved = (edits, personal)
        raise FakeError("daemon.json missing")


@pytest.fixture(autouse=True)
def fake_daemon(monkeypatch):
    module = types.SimpleNamespace(DaemonClient=FakeClient, DaemonError=FakeError)
    monkeypatch.setitem(sys.modules, "analysis_chamber.daemon", module)


@pytest.mark.asyncio
async def test_tools_and_error_mapping(tmp_path):
    async with Client(build_server(tmp_path)) as client:
        tools = await client.list_tools()
        assert {t.name for t in tools.tools} == {
            "chamber_start",
            "chamber_approve",
            "chamber_status",
            "chamber_list",
            "chamber_ask",
        }
        ok = await client.call_tool("chamber_start", {"question": "q"})
        assert not ok.is_error
        bad = await client.call_tool("chamber_approve", {"run": "r1", "personal": False})
        assert bad.is_error
        assert "daemon.json missing" in bad.content[0].text
        # Defaults reach the daemon as "no edits" and "personal not answered".
        await client.call_tool("chamber_approve", {"run": "r1"})
        assert FakeClient.approved == (None, None)
