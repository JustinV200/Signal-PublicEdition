"""LoadingBox: the "Claude is thinking" placeholder shown on the board while a turn runs.

It is one scene item of kind "loading" with the reserved id LOADING_ID, so the
board page renders it like any item. The board agent calls show() when a turn
starts and hide() when the first drawing lands or the turn ends; board_placeholder
moves it through the normal item patch. hide() looks at the scene, not at a flag,
so it also clears a stale box left in scene.json by a crashed daemon.
"""

import logging

from whiteboard.agent.board_change import BoundingBox
from whiteboard.display.scene import LOADING_ID, LOADING_KIND, Item, ItemNotFoundError, Style
from whiteboard.display.server import BoardController

logger = logging.getLogger(__name__)

LOADING_LABEL = "Claude is thinking…"
BOX_WIDTH = 260
BOX_HEIGHT = 70
# Gap between the changed region and the box.
BOX_MARGIN = 16
# Only a thin dashed outline and a label are lit: the box stays black inside.
LOADING_STYLE = Style(color="#8fe9ff")


def place_beside(
    changed: BoundingBox | None, stage: tuple[float, float]
) -> tuple[float, float, float, float]:
    """Pick the box position: right of the changed region, else below it, clamped to the board.

    Args:
        changed: (x, y, w, h) of the changed ink, or None if unknown (top-right corner).
        stage: The board's (width, height).

    Returns:
        (x, y, w, h) of the loading box.
    """
    width, height = stage
    if changed is None:
        x, y = width - BOX_WIDTH - BOX_MARGIN, BOX_MARGIN
    else:
        cx, cy, cw, ch = changed
        x, y = cx + cw + BOX_MARGIN, cy
        if x + BOX_WIDTH > width:
            x, y = cx, cy + ch + BOX_MARGIN
    x = max(0.0, min(x, width - BOX_WIDTH))
    y = max(0.0, min(y, height - BOX_HEIGHT))
    return (x, y, BOX_WIDTH, BOX_HEIGHT)


class LoadingBox:
    """Shows and removes the board's single loading placeholder."""

    def __init__(self, board: BoardController) -> None:
        """Args: board: The live board whose scene holds the placeholder."""
        self._board = board

    async def show(self, changed: BoundingBox | None) -> None:
        """Put the placeholder beside the changed region (replaces any existing one).

        Errors are logged, not raised: a missing placeholder must never stop a turn.
        """
        stage = self._board.stage()
        x, y, w, h = place_beside(changed, (stage["width"], stage["height"]))
        item = Item(
            id=LOADING_ID,
            kind=LOADING_KIND,
            x=x,
            y=y,
            w=w,
            h=h,
            content=LOADING_LABEL,
            style=LOADING_STYLE,
            created_by="daemon",
        )
        try:
            await self._board.put_item(item)
        except Exception:
            logger.exception("Couldn't show the loading box")

    async def hide(self) -> None:
        """Remove the placeholder if it is on the board. Safe to call any number of times."""
        if not any(i.id == LOADING_ID and i.kind == LOADING_KIND for i in self._board.scene.items):
            return
        try:
            await self._board.remove_item(LOADING_ID)
        except ItemNotFoundError:
            pass  # Removed by someone else (board_clear) between the check and now.
        except Exception:
            logger.exception("Couldn't remove the loading box")
