"""LoadingBox placement, stale cleanup and the reserved id."""

import pytest

from whiteboard.daemon.loading_box import (
    BOX_HEIGHT,
    BOX_MARGIN,
    BOX_WIDTH,
    LoadingBox,
    place_beside,
)
from whiteboard.display.scene import LOADING_ID, SceneError, SceneStore, item_from_dict
from whiteboard.display.server import BoardController

pytestmark = pytest.mark.asyncio

STAGE = (1280, 720)
SMALL = {"x": 0, "y": 0, "w": 9, "h": 9, "content": "x"}


async def test_placed_right_then_below_and_clamped_to_the_board() -> None:
    assert place_beside((100, 100, 50, 50), STAGE)[:2] == (100 + 50 + BOX_MARGIN, 100)
    # No room on the right: below the changed region.
    x, y, _, _ = place_beside((1100, 100, 150, 50), STAGE)
    assert (x, y) == (1280 - BOX_WIDTH, 100 + 50 + BOX_MARGIN)
    # Near the bottom-right corner, still inside the board.
    x, y, w, h = place_beside((1200, 700, 80, 20), STAGE)
    assert x + w <= 1280 and y + h <= 720 and h == BOX_HEIGHT


async def test_a_stale_box_in_scene_json_is_removed_on_start_but_other_items_stay(tmp_path) -> None:
    path = tmp_path / "scene.json"
    first = BoardController(SceneStore(path))
    await first.put_item(item_from_dict({"kind": "text", "id": "t1", **SMALL}))
    await LoadingBox(first).show(None)
    restarted = BoardController(SceneStore(path))
    assert LOADING_ID in [item.id for item in restarted.scene.items]
    await LoadingBox(restarted).hide()
    assert [item.id for item in restarted.scene.items] == ["t1"]
    assert [item.id for item in BoardController(SceneStore(path)).scene.items] == ["t1"]


async def test_the_loading_id_is_reserved_for_the_loading_kind() -> None:
    with pytest.raises(SceneError):
        item_from_dict({"kind": "text", "id": LOADING_ID, **SMALL})
    assert item_from_dict({"kind": "loading", **SMALL}).id == LOADING_ID
