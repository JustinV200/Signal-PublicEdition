"""Tests for the board agent's permission routing: what runs silently and what asks the owner."""

from pathlib import Path

import pytest

from whiteboard.agent import PermissionRouter

pytestmark = pytest.mark.asyncio

SNAPSHOT = Path(r"C:\src\Signal\tools\whiteboard\.state\snapshots\snapshot-1.png")


class FakeDialog:
    """Stands in for the owner dialog: records questions and gives a fixed answer."""

    def __init__(self, answer: bool | Exception) -> None:
        self.answer = answer
        self.questions: list[str] = []

    def __call__(self, question: str) -> bool:
        self.questions.append(question)
        if isinstance(self.answer, Exception):
            raise self.answer
        return self.answer


def router_for_turn(dialog: FakeDialog) -> PermissionRouter:
    """A router whose current turn's snapshot is SNAPSHOT."""
    router = PermissionRouter(dialog)
    router.allow_snapshot_read(SNAPSHOT)
    return router


@pytest.mark.parametrize(
    ("tool_name", "tool_input"),
    [
        ("mcp__whiteboard__board_draw", {"kind": "text"}),
        ("mcp__audiohub__notify", {"text": "done"}),
        # MCP tools are deferred, so the agent must load their schemas first.
        ("ToolSearch", {"query": "select:mcp__whiteboard__board_draw", "max_results": 5}),
        ("Read", {"file_path": str(SNAPSHOT)}),
        # Same string after normalizing case and separators.
        ("Read", {"file_path": str(SNAPSHOT).upper().replace("\\", "/")}),
    ],
)
async def test_board_tools_and_the_exact_snapshot_run_without_asking(tool_name, tool_input) -> None:
    dialog = FakeDialog(answer=False)
    assert await router_for_turn(dialog).decide(tool_name, tool_input)
    assert dialog.questions == []


@pytest.mark.parametrize(
    ("tool_name", "tool_input", "blocked_path"),
    [
        ("Bash", {"command": "dir"}, None),
        ("mcp__audiohub__music_play", {}, None),
        # A look-alike server name must not ride on the whiteboard prefix.
        ("mcp__whiteboard__x__board_draw", {}, None),
        # Ticking todos writes the owner's life/ files; the board can't order that alone.
        ("mcp__whiteboard__board_todo_done", {"item": "A19"}, None),
        ("mcp__whiteboard__board_todo_undone", {"item": "A19"}, None),
        # The night view is sleep mode's: the board can't dim the room or light it up.
        ("mcp__whiteboard__board_night_show", {"sky": True}, None),
        ("mcp__whiteboard__board_night_hide", {}, None),
        # Every other repo read asks, however harmless it looks.
        ("Read", {"file_path": "tools/whiteboard/README.md"}, None),
        ("Glob", {"pattern": "**/*.py"}, None),
        ("Grep", {"pattern": "def ", "path": "tools", "glob": "*.toml"}, None),
        # Windows aliases of the snapshot (or of anything) never match the exact string.
        ("Read", {"file_path": str(SNAPSHOT) + "."}, None),
        ("Read", {"file_path": str(SNAPSHOT) + "::$DATA"}, None),
        (
            "Read",
            {"file_path": r"C:\src\Signal\tools\WHITEB~1\.state\snapshots\snapshot-1.png"},
            None,
        ),
        ("Read", {"file_path": "tools/whiteboard/.state/snapshots/snapshot-1.png"}, None),
        ("Read", {"file_path": str(SNAPSHOT)}, "C:/elsewhere"),
    ],
)
async def test_everything_else_asks_and_follows_the_answer(
    tool_name, tool_input, blocked_path
) -> None:
    dialog = FakeDialog(answer=True)
    assert await router_for_turn(dialog).decide(tool_name, tool_input, blocked_path)
    assert len(dialog.questions) == 1
    assert tool_name in dialog.questions[0]


async def test_no_and_a_failed_dialog_both_deny() -> None:
    assert not await PermissionRouter(FakeDialog(False)).decide("Bash", {})
    assert not await PermissionRouter(FakeDialog(OSError("no desktop"))).decide("Bash", {})
