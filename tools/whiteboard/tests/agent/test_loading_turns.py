"""The thinking box: shown at turn start, gone on first draw, error, cancel and verify."""

import asyncio
import base64
from pathlib import Path
from typing import Any

import pytest

from whiteboard.agent import BoardAgent, TriageDecision
from whiteboard.daemon.loading_box import LoadingBox
from whiteboard.display.scene import LOADING_ID, SceneStore
from whiteboard.display.server import BoardController

pytestmark = pytest.mark.asyncio

TINY_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
)


class ScriptedSession:
    """Runs `script(on_first_change)` as the turn; the script can draw, fail or hang."""

    def __init__(self, script: Any) -> None:
        self._script = script

    async def connect(self) -> None:
        pass

    async def disconnect(self) -> None:
        pass

    async def run_turn(self, message: dict[str, Any], on_first_change: Any = None) -> bool:
        return await self._script(on_first_change)


def loading_ids(board: BoardController) -> list[str]:
    return [item.id for item in board.scene.items if item.id == LOADING_ID]


async def run_change(
    tmp_path: Path, session: Any, board: BoardController | None = None, **options: Any
) -> BoardController:
    """Feed one change to an agent with a real LoadingBox; stopping it cancels a hung turn."""
    board = board or BoardController(SceneStore(tmp_path / "scene.json"))
    png = tmp_path / "1.png"
    png.write_bytes(TINY_PNG)
    agent = BoardAgent(session, list, loading=LoadingBox(board), **options)
    await agent.start()
    try:
        agent.on_board_changed(png, (100, 100, 50, 50))
        await asyncio.sleep(0.3)
    finally:
        await agent.stop()
    return board


async def test_shown_at_turn_start_and_removed_when_the_first_draw_lands(tmp_path) -> None:
    seen: dict[str, Any] = {}
    board = BoardController(SceneStore(tmp_path / "scene.json"))

    async def script(on_first_change: Any) -> bool:
        seen["before"] = loading_ids(board)
        await on_first_change()
        seen["after_draw"] = loading_ids(board)
        await asyncio.sleep(10)  # Still working after the first draw.
        return True

    await run_change(tmp_path, ScriptedSession(script), board)
    assert (seen["before"], seen["after_draw"]) == ([LOADING_ID], [])


async def test_removed_after_an_error_or_cancel(tmp_path) -> None:
    async def fails(on_first_change: Any) -> bool:
        raise RuntimeError("cli crashed")

    async def hangs(on_first_change: Any) -> bool:
        await asyncio.sleep(10)
        return False

    assert loading_ids(await run_change(tmp_path, ScriptedSession(fails))) == []
    # run_change stops the agent mid-turn, which cancels the hanging turn.
    assert loading_ids(await run_change(tmp_path, ScriptedSession(hangs))) == []


async def test_not_present_during_the_verify_look(tmp_path) -> None:
    board = BoardController(SceneStore(tmp_path / "scene.json"))
    during_look: list[list[str]] = []

    async def drew(on_first_change: Any) -> bool:
        return True  # Never reports a first change: the end of the turn must hide the box.

    async def look() -> Path:
        during_look.append(loading_ids(board))
        return tmp_path / "1.png"

    await run_change(tmp_path, ScriptedSession(drew), board, look=look)
    assert during_look == [[]]


async def test_never_shown_when_triage_says_no(tmp_path) -> None:
    async def triage(change: Any, items: Any) -> TriageDecision:
        return TriageDecision(False, "notes")

    async def never(on_first_change: Any) -> bool:
        raise AssertionError("no turn expected")

    board = await run_change(tmp_path, ScriptedSession(never), triage=triage)
    assert loading_ids(board) == []
