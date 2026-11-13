"""Tests for BoardAgent's turn loop: one turn at a time, changes coalesced mid-turn, recovery."""

import asyncio
import base64
from pathlib import Path
from typing import Any

import pytest

from whiteboard.agent import BoardAgent, TriageDecision

pytestmark = pytest.mark.asyncio

# A 1x1 PNG: enough for the agent to read the snapshot's size and embed it.
TINY_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
)
WAIT_S = 2.0


class FakeSession:
    """A TurnSession whose turns block until the test releases them."""

    def __init__(self, failing_turns: int = 0) -> None:
        self.messages: list[dict[str, Any]] = []
        self.connects = 0
        self.turn_started = asyncio.Event()
        self.release = asyncio.Event()
        self._failing_turns = failing_turns

    async def connect(self) -> None:
        self.connects += 1

    async def disconnect(self) -> None:
        pass

    async def run_turn(self, message: dict[str, Any], on_first_change: Any = None) -> None:
        self.messages.append(message)
        self.turn_started.set()
        await self.release.wait()
        self.release.clear()
        if self._failing_turns:
            self._failing_turns -= 1
            raise RuntimeError("cli crashed")


def snapshot(tmp_path: Path, name: str) -> Path:
    path = tmp_path / name
    path.write_bytes(TINY_PNG)
    return path


def turn_text(message: dict[str, Any]) -> str:
    return message["message"]["content"][1]["text"]


async def next_turn(session: FakeSession) -> None:
    await asyncio.wait_for(session.turn_started.wait(), WAIT_S)
    session.turn_started.clear()


async def test_changes_during_a_turn_coalesce_into_one_next_turn(tmp_path) -> None:
    session = FakeSession()
    readable_snapshots: list[Path] = []
    triaged = []

    async def triage(change, items):
        triaged.append(change)
        return TriageDecision(True, "test")

    agent = BoardAgent(
        session,
        lambda: [{"id": "a1", "kind": "text", "content": "hi"}],
        allow_snapshot_read=readable_snapshots.append,
        triage=triage,
    )
    await agent.start()
    try:
        agent.on_board_changed(snapshot(tmp_path, "1.png"), (10, 10, 5, 5))
        await next_turn(session)
        # Two more changes land while the first turn is still running.
        agent.on_board_changed(snapshot(tmp_path, "2.png"), (100, 100, 10, 10))
        agent.on_board_changed(snapshot(tmp_path, "3.png"), (50, 200, 10, 20))
        await asyncio.sleep(0)
        session.release.set()
        await next_turn(session)
        session.release.set()
        await asyncio.sleep(0.05)
    finally:
        await agent.stop()
    assert len(session.messages) == 2
    first, second = session.messages
    assert first["message"]["content"][0]["type"] == "image"
    assert "a1" in turn_text(first)
    # The coalesced turn carries the newest snapshot and a box covering both changes.
    assert "3.png" in turn_text(second)
    assert "x=50, y=100, w=60, h=120" in turn_text(second)
    # Each turn may Read only its own snapshot.
    assert [path.name for path in readable_snapshots] == ["1.png", "3.png"]
    # The merged change compares against the snapshot before the OLDEST merged change.
    assert triaged[1].before_path.name == "1.png"


async def test_a_failed_turn_reconnects_and_the_next_change_still_runs(tmp_path) -> None:
    session = FakeSession(failing_turns=1)
    agent = BoardAgent(session, list)
    await agent.start()
    try:
        agent.on_board_changed(snapshot(tmp_path, "1.png"))
        await next_turn(session)
        session.release.set()
        await asyncio.sleep(0.05)
        agent.on_board_changed(snapshot(tmp_path, "2.png"))
        await next_turn(session)
        session.release.set()
    finally:
        await agent.stop()
    assert session.connects == 2
    assert len(session.messages) == 2


async def test_a_hung_turn_times_out_and_frees_the_agent(tmp_path) -> None:
    # The session never releases the turn, like a stuck CLI.
    session = FakeSession()
    agent = BoardAgent(session, list, turn_timeout_s=0.05)
    await agent.start()
    try:
        agent.on_board_changed(snapshot(tmp_path, "1.png"))
        await next_turn(session)
        await asyncio.sleep(0.2)
        assert not agent.is_busy
        agent.on_board_changed(snapshot(tmp_path, "2.png"))
        await next_turn(session)
    finally:
        await agent.stop()
    assert session.connects == 2
