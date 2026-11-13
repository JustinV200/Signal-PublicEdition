"""The idle view's clock flip counts as a page change, so the camera never takes it for drawing."""

import math
import time
from datetime import datetime
from pathlib import Path

import pytest

from whiteboard.display.scene import SceneStore
from whiteboard.display.server import BoardController
from whiteboard.display.server.board.minute import last_minute_boundary_s


@pytest.mark.parametrize(
    ("wall", "expected"),
    [
        (datetime(2026, 10, 20, 14, 2, 0), 1000.0),
        (datetime(2026, 10, 20, 14, 2, 59, 500_000), 940.5),
    ],
)
def test_last_minute_boundary_is_how_far_into_the_minute_the_clock_is(
    wall: datetime, expected: float
) -> None:
    assert last_minute_boundary_s(1000.0, wall) == pytest.approx(expected)


@pytest.mark.asyncio
async def test_page_changed_counts_minute_flips_only_while_idle(tmp_path: Path) -> None:
    board = BoardController(SceneStore(tmp_path / "scene.json"))
    assert board.page_changed_s() == -math.inf
    await board.set_view("idle")
    # The view switch itself was a push; a minute later only the flip moves it on.
    board._changed_s = -math.inf
    assert time.monotonic() - 60.0 <= board.page_changed_s() <= time.monotonic()
    await board.set_view("items")
    board._changed_s = -math.inf
    assert board.page_changed_s() == -math.inf
