"""The idle view's news ticker band, which the camera's motion check leaves out: it
covers the page's NEWS footer, sits where the page draws it, and only while idle shows."""

import re
from pathlib import Path

import pytest

from whiteboard.display import STATIC_DIR
from whiteboard.display.scene import SceneStore
from whiteboard.display.server import BoardController
from whiteboard.display.server.board.idle_ticker import (
    DESIGN_HEIGHT,
    DESIGN_WIDTH,
    TICKER_BAND,
)

NEWS_BOX = re.compile(r"news: \{ x: (\d+), y: (\d+), w: (\d+), h: (\d+) \}")
DESIGN_SIZE = re.compile(r"DESIGN = \{ width: (\d+), height: (\d+) \}")


def test_the_band_matches_the_pages_design_size_and_covers_its_footer() -> None:
    # Guards drift between layout.js and the Python copies of its size and footer.
    layout = (STATIC_DIR / "idle" / "layout.js").read_text(encoding="utf-8")
    design = DESIGN_SIZE.search(layout)
    assert design, "DESIGN not found in layout.js"
    assert tuple(map(int, design.groups())) == (DESIGN_WIDTH, DESIGN_HEIGHT)
    match = NEWS_BOX.search(layout)
    assert match, "LAYOUT.news not found in layout.js"
    x, y, w, h = map(int, match.groups())
    band_x, band_y, band_w, band_h = TICKER_BAND
    assert band_x < x and band_y < y and x + w < band_x + band_w and y + h < band_y + band_h


@pytest.mark.asyncio
async def test_motion_masks_hold_the_band_only_while_the_idle_view_shows(tmp_path: Path) -> None:
    board = BoardController(SceneStore(tmp_path / "scene.json"))
    assert board.motion_masks() == ()
    await board.set_view("idle")
    # The 1280x720 unfitted stage: the 1112x720 design at scale 1, centred (84 px each side).
    band_x, band_y, band_w, band_h = TICKER_BAND
    expected = ((84 + band_x) / 1280, band_y / 720, band_w / 1280, band_h / 720)
    assert board.motion_masks() == (pytest.approx(expected),)
    await board.set_view("todo")
    assert board.motion_masks() == ()
