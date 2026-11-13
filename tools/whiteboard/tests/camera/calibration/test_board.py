"""Tests for the board fit: the board quad is found in a synthetic frame, and its
corners map camera -> projector -> board view consistently."""

import cv2
import numpy as np

from whiteboard.camera import (
    Calibration,
    board_quad_in_projector,
    detect_board_quad,
    fit_board,
    view_transform,
)

# The board in the camera frame, TL, TR, BR, BL: tilted and keystoned.
BOARD_IN_CAMERA = np.float32([[420, 210], [1530, 260], [1490, 880], [450, 850]])
BOARD_TRIM_PX = 20
# A plausible camera -> projector homography.
CAMERA_TO_PROJECTOR = cv2.getPerspectiveTransform(
    np.float32([[300, 150], [1700, 200], [1650, 950], [330, 1000]]),
    np.float32([[0, 0], [1280, 0], [1280, 720], [0, 720]]),
)


def synthetic_board_frame(wall_brightness: int = 70) -> np.ndarray:
    """A bright quad with some ink on it, on a wall, with camera noise.

    A bright wall (wall_brightness > Otsu's split) runs off the top and right of
    the frame and is bigger than the board; dark trim separates the two, and the
    floor below stays dark.
    """
    frame = np.full((1080, 1920), 70, np.uint8)
    if wall_brightness != 70:
        frame[:1000, 150:] = wall_brightness
        trim = cv2.convexHull(BOARD_IN_CAMERA).astype(np.int32)
        cv2.polylines(frame, [trim], True, 60, BOARD_TRIM_PX * 2)
    cv2.fillConvexPoly(frame, BOARD_IN_CAMERA.astype(np.int32), 215)
    cv2.putText(frame, "x = 2y", (600, 500), cv2.FONT_HERSHEY_SIMPLEX, 3, 40, 6)
    noise = np.random.default_rng(5).normal(0, 4, frame.shape)
    return cv2.cvtColor(np.clip(frame + noise, 0, 255).astype(np.uint8), cv2.COLOR_GRAY2BGR)


def make_calibration() -> Calibration:
    return Calibration(CAMERA_TO_PROJECTOR, (1920, 1080), (1280, 720), 0.3, 6, "2026-10-19")


def test_board_quad_is_found_in_corner_order() -> None:
    quad = detect_board_quad(synthetic_board_frame(), make_calibration())

    assert quad is not None
    assert np.abs(quad - BOARD_IN_CAMERA).max() < 3


def test_the_board_wins_over_a_bigger_bright_wall_hugging_the_frame() -> None:
    quad = detect_board_quad(synthetic_board_frame(wall_brightness=200), make_calibration())

    assert quad is not None
    assert np.abs(quad - BOARD_IN_CAMERA).max() < BOARD_TRIM_PX / 2


def test_no_board_in_a_uniform_frame() -> None:
    assert detect_board_quad(np.full((1080, 1920, 3), 120, np.uint8), make_calibration()) is None


def test_corners_round_trip_and_land_on_the_board_view_corners() -> None:
    quad_projector = board_quad_in_projector(BOARD_IN_CAMERA, CAMERA_TO_PROJECTOR)
    back = cv2.perspectiveTransform(
        quad_projector.reshape(-1, 1, 2), np.linalg.inv(CAMERA_TO_PROJECTOR)
    ).reshape(4, 2)
    assert np.abs(back - BOARD_IN_CAMERA).max() < 0.01

    fitted = fit_board(make_calibration(), BOARD_IN_CAMERA, height=720)
    camera_to_view, (width, height) = view_transform(fitted)
    corners = cv2.perspectiveTransform(BOARD_IN_CAMERA.reshape(-1, 1, 2), camera_to_view)
    expected = np.float32([[0, 0], [width, 0], [width, height], [0, height]])
    assert height == 720 and fitted.board_size == (width, height)
    assert np.abs(corners.reshape(4, 2) - expected).max() < 0.01
