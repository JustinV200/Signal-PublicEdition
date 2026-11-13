"""Triage skips useless turns and fails open; a draw earns exactly one verify turn."""

import asyncio
import base64
from pathlib import Path
from typing import Any

import pytest

from whiteboard.agent import BoardAgent, Triage

pytestmark = pytest.mark.asyncio

TINY_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
)


class FakeSession:
    """Records turns; each returns whether it 'drew', from a script."""

    def __init__(self, draws: list[Any]) -> None:
        self.messages: list[dict[str, Any]] = []
        self.events: list[str] = []
        self._draws = draws

    async def connect(self) -> None:
        self.events.append("connect")

    async def disconnect(self) -> None:
        self.events.append("disconnect")

    async def run_turn(self, message: dict[str, Any], on_first_change: Any = None) -> bool:
        self.events.append("turn")
        self.messages.append(message)
        draw = self._draws.pop(0)
        if isinstance(draw, Exception):
            raise draw
        return draw


def fake_ask(reply: str | Exception | None):
    """A fake SDK call: returns `reply`, raises it, or hangs when None."""

    async def ask(message: dict[str, Any], model: str) -> tuple[str, float | None]:
        if reply is None:
            await asyncio.sleep(10)
        if isinstance(reply, Exception):
            raise reply
        return reply, 0.001

    return ask


async def run_one_change(tmp_path: Path, session: FakeSession, **options: Any) -> None:
    png = tmp_path / "1.png"
    png.write_bytes(TINY_PNG)
    agent = BoardAgent(session, list, **options)
    await agent.start()
    try:
        agent.on_board_changed(png, (1, 1, 2, 2))
        await asyncio.sleep(0.2)
    finally:
        await agent.stop()


@pytest.mark.parametrize(
    ("reply", "turns"),
    [
        ('{"act": false, "reason": "shadow"}', 0),
        ('noise {"act": true, "reason": "request"} noise', 1),
        (RuntimeError("cli died"), 1),
        (None, 1),  # times out
        ("not json at all", 1),
        ('{"act": "no"}', 1),
    ],
)
async def test_triage_decides_and_fails_open(tmp_path, reply, turns) -> None:
    session = FakeSession([False])
    triage = Triage("haiku", 0.05, fake_ask(reply))
    await run_one_change(tmp_path, session, triage=triage)
    assert len(session.messages) == turns


async def test_hostile_json_fails_open_and_the_worker_survives(tmp_path) -> None:
    # Regression: deeply nested JSON raised RecursionError outside the try and killed the worker.
    nested = "[" * 100000 + "]" * 100000
    session = FakeSession([False, False])
    png = tmp_path / "1.png"
    png.write_bytes(TINY_PNG)
    agent = BoardAgent(session, list, triage=Triage("haiku", 5, fake_ask(nested)))
    await agent.start()
    try:
        agent.on_board_changed(png)
        await asyncio.sleep(0.2)
        agent.on_board_changed(png)
        await asyncio.sleep(0.2)
    finally:
        await agent.stop()
    assert len(session.messages) == 2


async def test_triage_off_always_runs_the_turn(tmp_path) -> None:
    session = FakeSession([False])
    await run_one_change(tmp_path, session, triage=None)
    assert len(session.messages) == 1


async def test_triage_sees_the_image_bbox_and_items(tmp_path) -> None:
    seen: list[dict[str, Any]] = []

    async def ask(message: dict[str, Any], model: str) -> tuple[str, float | None]:
        seen.append(message)
        return '{"act": true, "reason": "ok"}', None

    png = tmp_path / "1.png"
    png.write_bytes(TINY_PNG)
    agent = BoardAgent(
        FakeSession([False]), lambda: [{"id": "a1", "kind": "text"}], triage=Triage("haiku", 5, ask)
    )
    await agent.start()
    try:
        agent.on_board_changed(png, (1, 1, 2, 2))
        await asyncio.sleep(0.2)
    finally:
        await agent.stop()
    blocks = seen[0]["message"]["content"]
    assert blocks[0]["type"] == "image"
    assert "x=1, y=1, w=2, h=2" in blocks[1]["text"] and "a1" in blocks[1]["text"]


async def test_a_turn_that_drew_gets_one_verify_turn_that_never_chains(tmp_path) -> None:
    looks = 0

    async def look() -> Path:
        nonlocal looks
        looks += 1
        return tmp_path / "1.png"

    # Both turns report drawing; the verify turn's draw must not start a third.
    session = FakeSession([True, True])
    await run_one_change(tmp_path, session, look=look)
    assert len(session.messages) == 2 and looks == 1
    # The verify turn runs in the same session as the turn it checks.
    assert session.events == ["connect", "turn", "turn", "disconnect"]
    assert "how your drawing actually looks" in session.messages[1]["message"]["content"][1]["text"]


async def test_no_draw_or_no_look_means_no_verify_turn(tmp_path) -> None:
    async def look() -> Path:
        return tmp_path / "1.png"

    no_draw = FakeSession([False])
    await run_one_change(tmp_path, no_draw, look=look)
    switched_off = FakeSession([True])
    await run_one_change(tmp_path, switched_off, look=None)
    assert len(no_draw.messages) == 1 and len(switched_off.messages) == 1


async def test_only_successful_board_changing_tool_calls_count_as_drawing() -> None:
    from claude_agent_sdk import AssistantMessage, ToolResultBlock, ToolUseBlock, UserMessage

    from whiteboard.agent.sdk_session import _track_board_changes

    pending: set[str] = set()
    call = ToolUseBlock(id="t1", name="mcp__whiteboard__board_draw", input={})
    look = ToolUseBlock(id="t2", name="mcp__whiteboard__board_look", input={})
    assistant = AssistantMessage(content=[call, look], model="m")
    assert _track_board_changes(assistant, pending) is False

    def result(tool_id: str, is_error: bool) -> UserMessage:
        return UserMessage(content=[ToolResultBlock(tool_use_id=tool_id, is_error=is_error)])

    assert _track_board_changes(result("t1", True), pending) is False
    assert _track_board_changes(result("t2", False), pending) is False
    assert _track_board_changes(result("t1", False), pending) is True


async def test_each_change_gets_its_own_session_closed_even_after_an_error(tmp_path) -> None:
    session = FakeSession([RuntimeError("cli crashed"), False])
    png = tmp_path / "1.png"
    png.write_bytes(TINY_PNG)
    agent = BoardAgent(session, list)
    await agent.start()
    try:
        agent.on_board_changed(png)
        await asyncio.sleep(0.1)
        agent.on_board_changed(png)
        await asyncio.sleep(0.1)
    finally:
        await agent.stop()
    assert session.events == ["connect", "turn", "disconnect"] * 2


async def test_triage_sends_before_and_after_crops_when_there_is_a_previous_snapshot(
    tmp_path,
) -> None:
    import cv2
    import numpy as np

    from whiteboard.agent.board_change import BoardChange
    from whiteboard.agent.crops import padded_box
    from whiteboard.agent.triage import build_triage_message

    before, after = np.full((100, 200, 3), 255, np.uint8), np.full((100, 200, 3), 255, np.uint8)
    after[40:50, 100:120] = 0
    paths = [tmp_path / "before.png", tmp_path / "after.png"]
    for path, image in zip(paths, (before, after), strict=True):
        cv2.imwrite(str(path), image)

    message = build_triage_message(BoardChange(paths[1], (100, 40, 20, 10), paths[0]), [])
    blocks = message["message"]["content"]
    images = [b for b in blocks if b["type"] == "image"]
    assert len(images) == 3  # before, after, thumbnail
    assert "NEW" in blocks[-1]["text"]
    # 10% padding per side, clamped to the image.
    assert padded_box((100, 40, 20, 10), 200, 100) == (98, 39, 122, 51)
    assert padded_box((0, 0, 300, 300), 200, 100) == (0, 0, 200, 100)
    # A different-size "before" (e.g. after a recalibration) falls back to the whole board.
    cv2.imwrite(str(paths[0]), np.zeros((50, 50, 3), np.uint8))
    fallback = build_triage_message(BoardChange(paths[1], (100, 40, 20, 10), paths[0]), [])
    assert len(fallback["message"]["content"]) == 2
