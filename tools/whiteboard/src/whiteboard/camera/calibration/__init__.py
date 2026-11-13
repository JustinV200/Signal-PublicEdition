"""Public API of whiteboard.camera.calibration: markers, homography, board fit, rectify.

The rest of whiteboard.camera imports calibration features from here only.
"""

from whiteboard.camera.calibration.board import (
    board_quad_in_camera,
    board_quad_in_projector,
    board_view_size,
    detect_board_quad,
    fit_board,
)
from whiteboard.camera.calibration.markers import PROJECTOR_SIZE, pattern_layout
from whiteboard.camera.calibration.record import (
    Calibration,
    CalibrationError,
    load_calibration,
    save_calibration,
)
from whiteboard.camera.calibration.rectify import rectify, rectify_to_view, view_transform
from whiteboard.camera.calibration.solve import calibrate, solve_calibration

__all__ = [
    "PROJECTOR_SIZE",
    "Calibration",
    "CalibrationError",
    "board_quad_in_camera",
    "board_quad_in_projector",
    "board_view_size",
    "calibrate",
    "detect_board_quad",
    "fit_board",
    "load_calibration",
    "pattern_layout",
    "rectify",
    "rectify_to_view",
    "save_calibration",
    "solve_calibration",
    "view_transform",
]
