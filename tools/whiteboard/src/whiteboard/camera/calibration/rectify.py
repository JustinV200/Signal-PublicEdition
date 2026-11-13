"""Warping camera frames into the coordinate space Claude draws in.

Without a board fit, that space is the projector stage. With one, it's the
logical board: camera px -> projector px (the homography), then the board's
projector quad -> a straight width x height rectangle. Either way, `board_look`
images and `board_draw` coordinates line up.
"""

import cv2
import numpy as np

from whiteboard.camera.calibration.markers import PROJECTOR_SIZE
from whiteboard.camera.calibration.record import Calibration


def rectangle_corners(size: tuple[int, int]) -> np.ndarray:
    """A width x height rectangle's corners, ordered TL, TR, BR, BL."""
    width, height = size
    return np.array([[0, 0], [width, 0], [width, height], [0, height]], np.float32)


def rectify(
    frame: np.ndarray,
    homography: np.ndarray,
    size: tuple[int, int] = PROJECTOR_SIZE,
    scale: float = 1,
) -> np.ndarray:
    """Warp a camera frame through `homography` into a size-sized view.

    Args:
        frame: Camera frame.
        homography: 3x3 matrix from camera px to view px.
        size: (width, height) of the view.
        scale: Output pixels per view pixel; 2 doubles the resolution for legibility.

    Returns:
        The warped image, (height * scale) x (width * scale).
    """
    scaling = np.diag([scale, scale, 1.0])
    width, height = size
    output_size = (round(width * scale), round(height * scale))
    return cv2.warpPerspective(frame, scaling @ homography, output_size, flags=cv2.INTER_LINEAR)


def view_transform(calibration: Calibration) -> tuple[np.ndarray, tuple[int, int]]:
    """The camera-to-view matrix and view size: the board view if fitted, else the stage."""
    if calibration.board_quad is None or calibration.board_size is None:
        return calibration.homography, calibration.projector_size
    board_to_view = cv2.getPerspectiveTransform(
        calibration.board_quad.astype(np.float32), rectangle_corners(calibration.board_size)
    )
    return board_to_view @ calibration.homography, calibration.board_size


def rectify_to_view(
    frame: np.ndarray, calibration: Calibration | None, scale: float = 1
) -> tuple[np.ndarray, bool]:
    """Rectify `frame` with `calibration` when it applies to this frame.

    Returns:
        (image, is_rectified). With no calibration, or a frame whose size differs
        from the one calibration was solved on (so the homography doesn't apply),
        the raw frame comes back with is_rectified False.
    """
    if calibration is None:
        return frame, False
    frame_height, frame_width = frame.shape[:2]
    if (frame_width, frame_height) != calibration.camera_size:
        return frame, False
    homography, size = view_transform(calibration)
    return rectify(frame, homography, size, scale), True
