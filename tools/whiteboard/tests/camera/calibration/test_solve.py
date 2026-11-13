"""Tests for marker calibration: a known homography is recovered from a synthetic
camera view of the pattern; too few markers give a clear error."""

from pathlib import Path

import cv2
import numpy as np
import pytest

from whiteboard.camera import (
    CalibrationError,
    calibrate,
    load_calibration,
    rectify,
    save_calibration,
    solve_calibration,
)
from whiteboard.camera.calibration import markers, solve

CAMERA_SIZE = (1920, 1080)
# Where the stage corners land in the camera: off-centre and keystoned.
STAGE_IN_CAMERA = np.float32([[310, 170], [1650, 240], [1590, 930], [350, 980]])


def render_stage(visible_ids: set[int] | None = None) -> np.ndarray:
    """The pattern as the page draws it: black stage, white-margined marker tiles."""
    width, height = markers.PROJECTOR_SIZE
    stage = np.zeros((height, width), np.uint8)
    for placement in markers.marker_placements():
        if visible_ids is None or placement.id in visible_ids:
            tile = markers.render_tile(placement.id)
            stage[
                placement.y : placement.y + placement.size,
                placement.x : placement.x + placement.size,
            ] = tile
    return stage


def camera_view(stage: np.ndarray, stage_to_camera: np.ndarray) -> np.ndarray:
    """What the webcam sees: the stage warped, on a lit board, low contrast and noisy."""
    warped = cv2.warpPerspective(stage, stage_to_camera, CAMERA_SIZE).astype(np.float32)
    noise = np.random.default_rng(3).normal(0, 3, warped.shape)
    view = np.clip(70 + 0.65 * warped + noise, 0, 255).astype(np.uint8)
    return cv2.GaussianBlur(view, (3, 3), 0)


def stage_to_camera() -> np.ndarray:
    width, height = markers.PROJECTOR_SIZE
    stage_corners = np.float32([[0, 0], [width, 0], [width, height], [0, height]])
    return cv2.getPerspectiveTransform(stage_corners, STAGE_IN_CAMERA)


def test_known_homography_is_recovered(tmp_path: Path) -> None:
    truth = stage_to_camera()
    stage = render_stage()

    calibration = solve_calibration(camera_view(stage, truth))

    assert calibration.marker_count == 6
    assert calibration.camera_size == CAMERA_SIZE
    assert calibration.reprojection_error_px < 1.0
    grid = np.float32([[x, y] for x in range(0, 1281, 160) for y in range(0, 721, 120)])
    in_camera = cv2.perspectiveTransform(grid.reshape(-1, 1, 2), truth)
    back = cv2.perspectiveTransform(in_camera, calibration.homography).reshape(-1, 2)
    assert np.abs(back - grid).max() < 1.0
    rectified = rectify(camera_view(stage, truth), calibration.homography)
    assert rectified.shape == stage.shape
    # Back in stage space, marker pixels line up: bright where the tiles are white.
    assert np.mean(np.abs(rectified.astype(float) - (70 + 0.65 * stage))) < 12
    save_calibration(calibration, tmp_path / "calibration.json")
    loaded = load_calibration(tmp_path / "calibration.json")
    assert loaded is not None
    assert np.allclose(loaded.homography, calibration.homography)


@pytest.mark.parametrize(
    ("visible_ids", "message"),
    [(set(), "can't see the projected area"), ({0, 5}, "only 2 of 6")],
)
def test_too_few_markers_is_a_clear_error(visible_ids: set[int], message: str) -> None:
    view = camera_view(render_stage(visible_ids), stage_to_camera())

    with pytest.raises(CalibrationError, match=message):
        solve_calibration(view)


@pytest.mark.asyncio
async def test_calibrate_clears_the_pattern_when_it_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(solve, "PATTERN_SETTLE_S", 0)
    events: list[str] = []

    class BlankCamera:
        def read_fresh(self) -> np.ndarray:
            return np.zeros((1080, 1920), np.uint8)

    async def show_pattern() -> None:
        events.append("show")

    async def clear_pattern() -> None:
        events.append("clear")

    with pytest.raises(CalibrationError):
        await calibrate(BlankCamera(), show_pattern, clear_pattern)
    assert events == ["show", "clear"]
