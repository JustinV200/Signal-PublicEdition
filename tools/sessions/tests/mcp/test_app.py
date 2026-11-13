"""Tests for the sessions MCP server through an in-process mcp.Client, with a fake daemon."""

from pathlib import Path
from typing import Any

import pytest
from mcp import Client

from claude_sessions.config import Settings
from claude_sessions.ipc import DaemonRequestError
from claude_sessions.mcp import SERVER_NAME, SessionTools, build_server

pytestmark = pytest.mark.asyncio

EXPECTED_TOOLS = (
    "list_repos",
    "list_sessions",
    "start_session",
    "send_to_session",
    "session_status",
    "resume_session",
    "stop_session",
    "list_managed_sessions",
)


class FakeDaemon:
    """Records (op, args) and returns `reply`, or raises `error`."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.reply: Any = {"id": "s-1", "state": "working"}
        self.error: Exception | None = None

    async def __call__(self, op: str, args: dict[str, Any]) -> Any:
        self.calls.append((op, args))
        if self.error is not None:
            raise self.error
        return self.reply


@pytest.fixture
def fake_daemon() -> FakeDaemon:
    return FakeDaemon()


@pytest.fixture
def server(tmp_path: Path, fake_daemon: FakeDaemon, monkeypatch: pytest.MonkeyPatch):
    # Keep repo discovery away from the real ~/.claude/projects.
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "no-claude"))
    (tmp_path / "Projects" / "KeyForge" / ".git").mkdir(parents=True)
    settings = Settings(repo_roots=(tmp_path,), max_depth=3)
    return build_server(SessionTools(settings, fake_daemon))


def _text(result) -> str:
    return "".join(block.text for block in result.content)


async def test_lists_every_tool_and_points_live_sessions_at_send_message(server) -> None:
    async with Client(server) as client:
        assert client.server_info.name == SERVER_NAME == "sessions"
        tools = {tool.name: tool for tool in (await client.list_tools()).tools}

    assert tuple(tools) == EXPECTED_TOOLS
    for name in ("start_session", "send_to_session", "resume_session", "list_sessions"):
        assert "SendMessage" in tools[name].description
    modes = tools["start_session"].input_schema["properties"]["permission_mode"]["enum"]
    assert modes == ["default", "acceptEdits", "plan"]


async def test_start_session_resolves_a_repo_name_before_calling_the_daemon(
    server, fake_daemon: FakeDaemon, tmp_path: Path
) -> None:
    async with Client(server) as client:
        result = await client.call_tool(
            "start_session", {"repo": "keyforge", "prompt": "Run the tests.", "model": "sonnet"}
        )

    assert not result.is_error and '"s-1"' in _text(result)
    assert fake_daemon.calls == [
        (
            "start",
            {
                "repo": str((tmp_path / "Projects" / "KeyForge").resolve()),
                "prompt": "Run the tests.",
                "permission_mode": "default",
                "model": "sonnet",
            },
        )
    ]


async def test_failures_become_error_results_the_model_can_read(
    server, fake_daemon: FakeDaemon
) -> None:
    fake_daemon.error = DaemonRequestError("Session s-9 is working; wait until it's idle.")
    async with Client(server) as client:
        busy = await client.call_tool("send_to_session", {"id": "s-9", "prompt": "hi"})
        unknown = await client.call_tool("start_session", {"repo": "nope", "prompt": "hi"})

    assert busy.is_error and "wait until it's idle" in _text(busy)
    assert unknown.is_error and "No repo name matches 'nope'" in _text(unknown)
