"""BoardController.page_changed_s: what the change watcher settles after, so the
daemon's own blanks, marker flashes and drawings never trigger a capture."""

import math
import time
from pathlib import Path

import pytest

from whiteboard.display.scene import SceneStore
from whiteboard.display.server import BoardController, Highlight

pytestmark = pytest.mark.asyncio

HIGHLIGHT_S = 5.0


async def test_page_changed_s_covers_flashes_until_restored_and_highlights_until_they_end(
    tmp_path: Path,
) -> None:
    board = BoardController(SceneStore(tmp_path / "scene.json"))
    assert board.page_changed_s() == -math.inf

    await board.set_mode("blank")
    assert board.page_changed_s() == math.inf  # never settled while the page is blank

    before_restore = time.monotonic()
    await board.set_mode("normal")
    assert before_restore <= board.page_changed_s() <= time.monotonic()

    await board.highlight(Highlight(10, 10, 50, 50, HIGHLIGHT_S))
    assert board.page_changed_s() >= before_restore + HIGHLIGHT_S
