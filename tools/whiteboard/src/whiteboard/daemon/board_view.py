"""BoardViewSync: keeps the capture rig's calibration in step with the scene's board fit.

The scene's board_quad (display, saved in scene.json) is the one source of
truth for the fit, whoever set it: calibration, `whiteboard fit`, or a plain
POST /api/fit. calibration.json holds only the marker calibration. This class
combines the two into the Calibration the rig rectifies with, so board_look
images and board_draw coordinates always share one space.
"""

from dataclasses import replace

import numpy as np

from whiteboard.camera import Calibration, CaptureRig, board_view_size
from whiteboard.display.scene import Quad
from whiteboard.display.server import BoardController


def with_board_fit(
    marker_calibration: Calibration | None, quad: Quad | None, fit_height: int
) -> Calibration | None:
    """Combine a marker calibration with a board quad in projector px.

    Args:
        marker_calibration: Camera-to-projector calibration, or None if uncalibrated.
        quad: The board's corners in projector px (TL, TR, BR, BL), or None for no fit.
        fit_height: Logical board height ([display] fit_height); width follows the aspect.

    Returns:
        The calibration to rectify with, or None when there's no marker calibration.
    """
    if marker_calibration is None:
        return None
    if quad is None:
        return replace(marker_calibration, board_quad=None, board_size=None)
    quad_array = np.array(quad, dtype=np.float32)
    board_size = board_view_size(quad_array, fit_height)
    return replace(marker_calibration, board_quad=quad_array, board_size=board_size)


class BoardViewSync:
    """Owns the marker calibration and pushes the combined calibration into the rig."""

    def __init__(
        self,
        board: BoardController,
        rig: CaptureRig,
        fit_height: int,
        marker_calibration: Calibration | None,
    ) -> None:
        """Start synced with the saved scene.

        Args:
            board: Holds the scene and its board_quad.
            rig: The capture rig whose calibration this keeps current.
            fit_height: Logical board height for a fitted view.
            marker_calibration: Loaded from calibration.json, or None.
        """
        self._board = board
        self._rig = rig
        self._fit_height = fit_height
        self.marker_calibration = marker_calibration
        self._applied: tuple[Calibration | None, Quad | None] | None = None
        self.refresh()

    def set_marker_calibration(self, calibration: Calibration) -> None:
        """Use a newly solved marker calibration (its own board fields are ignored)."""
        self.marker_calibration = calibration
        self.refresh()

    def refresh(self) -> None:
        """Rebuild the rig's calibration if the marker calibration or the board quad changed.

        Only a real change replaces the rig's object, because the change watcher
        resets its baseline whenever that object changes.
        """
        quad = self._board.scene.board_quad
        current = (self.marker_calibration, quad)
        if (
            self._applied is not None
            and self._applied[0] is current[0]
            and self._applied[1] == quad
        ):
            return
        self._rig.calibration = with_board_fit(self.marker_calibration, quad, self._fit_height)
        self._applied = current

    async def set_mode(self, mode: str) -> None:
        """The rig's set_mode: refresh first, so every capture uses the current fit."""
        self.refresh()
        await self._board.set_mode(mode)
