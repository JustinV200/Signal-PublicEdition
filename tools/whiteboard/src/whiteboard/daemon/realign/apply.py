"""Putting a new alignment in place: save it, switch the rig, keep items put, say so.

The Realigner (realigner.py) decides what the new calibration and fit are;
this module only applies them, so a failed write leaves the old alignment.
"""

import asyncio
import contextlib
import logging

from whiteboard.camera import Calibration, save_calibration
from whiteboard.daemon.camera_hooks import HookContext
from whiteboard.display.scene import ItemNotFoundError, Quad, SceneError, item_from_dict
from whiteboard.display.server import BoardController
from whiteboard.saves import SaveError, scale_items

logger = logging.getLogger(__name__)

TOAST_ID = "realign-toast"
TOAST_TEXT = "Re-aligned to board"
TOAST_S = 3.0
# x, y, w, h in board px: a small banner in the top-left corner.
TOAST_BOX = (20, 20, 420, 56)
TOAST_AUTHOR = "whiteboard"


async def apply_alignment(context: HookContext, marker: Calibration, quad: Quad) -> None:
    """Save the fit and calibration, then switch the rig over and keep items in place.

    Raises:
        OSError: A save failed; the old fit is restored and the calibration untouched.
    """
    board = context.board
    old_size = _board_size(board)
    old_quad = board.scene.board_quad
    try:
        # set_fit saves before it changes anything, so a failure here changes nothing.
        await board.set_fit(quad)
        await asyncio.to_thread(save_calibration, marker, context.calibration_path)
    except OSError:
        await board.set_fit(old_quad)
        raise
    context.sync.set_marker_calibration(marker)
    await _keep_items_in_place(board, old_size)


async def flash_toast(board: BoardController) -> None:
    """Show TOAST_TEXT for TOAST_S, then remove it (also on cancel)."""
    x, y, w, h = TOAST_BOX
    toast = {"id": TOAST_ID, "kind": "text", "x": x, "y": y, "w": w, "h": h}
    await board.put_item(
        item_from_dict({**toast, "content": TOAST_TEXT, "created_by": TOAST_AUTHOR})
    )
    try:
        await asyncio.sleep(TOAST_S)
    finally:
        # Someone may have cleared the board meanwhile.
        with contextlib.suppress(ItemNotFoundError):
            await board.remove_item(TOAST_ID)


async def _keep_items_in_place(board: BoardController, old_size: tuple[int, int]) -> None:
    """Rescale items when the logical board size changed, so they stay on the same spot."""
    new_size = _board_size(board)
    if new_size == old_size or not board.scene.items:
        return
    try:
        await board.put_items(scale_items(board.scene.items, old_size, new_size), replace=True)
    except (SaveError, SceneError, OSError) as error:
        logger.warning("re-aligned, but couldn't rescale the items to the new board: %s", error)


def _board_size(board: BoardController) -> tuple[int, int]:
    """The logical board (width, height) in board px."""
    stage = board.stage()
    return stage["width"], stage["height"]
