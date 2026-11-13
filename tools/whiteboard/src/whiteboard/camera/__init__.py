"""Public API of whiteboard.camera: capture, calibration, clean capture, change and drift watching.

Other whiteboard packages import camera features from here only.
"""

from whiteboard.camera.calibration import (
    PROJECTOR_SIZE,
    Calibration,
    CalibrationError,
    board_quad_in_camera,
    board_quad_in_projector,
    board_view_size,
    calibrate,
    detect_board_quad,
    fit_board,
    load_calibration,
    pattern_layout,
    rectify,
    rectify_to_view,
    save_calibration,
    solve_calibration,
    view_transform,
)
from whiteboard.camera.camera import Camera
from whiteboard.camera.clean_capture import (
    BLANK_MODE,
    NORMAL_MODE,
    CaptureRig,
    CleanFrame,
    clean_capture,
    grab_clean_frame,
    keep_mode,
)
from whiteboard.camera.detection import (
    BORDER_NOISE_PX,
    added_and_erased_ink,
    added_ink_ratio,
    darker_than_board,
    ink_change,
)
from whiteboard.camera.device import CameraError, CameraInfo, list_cameras
from whiteboard.camera.drift import (
    BoardActivity,
    DriftMonitor,
    DriftReading,
    check_drift_now,
    corner_error,
)
from whiteboard.camera.movement import ReferencePhoto, camera_shift_px, homography_drift_px
from whiteboard.camera.watcher import BBox, ChangeWatcher, OnBoardChanged

__all__ = [
    "BLANK_MODE",
    "BORDER_NOISE_PX",
    "NORMAL_MODE",
    "PROJECTOR_SIZE",
    "BBox",
    "BoardActivity",
    "Calibration",
    "CalibrationError",
    "Camera",
    "CameraError",
    "CameraInfo",
    "CaptureRig",
    "CleanFrame",
    "ChangeWatcher",
    "DriftMonitor",
    "DriftReading",
    "OnBoardChanged",
    "ReferencePhoto",
    "added_and_erased_ink",
    "added_ink_ratio",
    "board_quad_in_camera",
    "board_quad_in_projector",
    "board_view_size",
    "calibrate",
    "camera_shift_px",
    "check_drift_now",
    "clean_capture",
    "corner_error",
    "darker_than_board",
    "detect_board_quad",
    "fit_board",
    "grab_clean_frame",
    "homography_drift_px",
    "ink_change",
    "keep_mode",
    "list_cameras",
    "load_calibration",
    "pattern_layout",
    "rectify",
    "rectify_to_view",
    "save_calibration",
    "solve_calibration",
    "view_transform",
]
