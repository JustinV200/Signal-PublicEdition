"""Calibration: show the marker pattern, find it in the camera, fit the homography.

`calibrate()` is what the daemon's POST /api/calibrate runs. It drives the page
through the async callbacks it's given and reads frames from the camera.
`solve_calibration()` is the pure part: one camera frame in, a Calibration out.
"""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Protocol

import cv2
import numpy as np

from whiteboard.camera.calibration.markers import (
    PROJECTOR_SIZE,
    MarkerPlacement,
    aruco_dictionary,
    marker_placements,
)
from whiteboard.camera.calibration.record import Calibration, CalibrationError

logger = logging.getLogger(__name__)

# Fewer markers than this leaves too few, too clustered points for a stable fit.
MIN_MARKERS = 3
# RANSAC inlier distance, in projector px.
RANSAC_THRESHOLD_PX = 3.0
# Time for the page to show the pattern and the camera's auto-exposure to settle.
PATTERN_SETTLE_S = 1.0
# Frames tried before giving up; exposure can still be adjusting on the first.
DETECT_ATTEMPTS = 4
NO_MARKERS_MESSAGE = (
    "camera can't see the projected area; aim it at the board so the whole projection is in view"
)


class FreshFrameSource(Protocol):
    """Anything that can return a frame exposed after the call (e.g. Camera)."""

    def read_fresh(self) -> np.ndarray: ...


def detect_markers(frame: np.ndarray) -> dict[int, np.ndarray]:
    """Find ArUco markers in a camera frame (BGR or grayscale).

    Returns:
        Marker id -> its 4 corners in camera px, float32 (4, 2), ordered TL, TR, BR, BL.
    """
    gray = frame if frame.ndim == 2 else cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    parameters = cv2.aruco.DetectorParameters()
    # Sub-pixel corners make the fit noticeably more accurate.
    parameters.cornerRefinementMethod = cv2.aruco.CORNER_REFINE_SUBPIX
    detector = cv2.aruco.ArucoDetector(aruco_dictionary(), parameters)
    corners, ids, _rejected = detector.detectMarkers(gray)
    if ids is None:
        return {}
    pairs = zip(ids.ravel(), corners, strict=True)
    return {int(marker_id): marker_corners.reshape(4, 2) for marker_id, marker_corners in pairs}


def _matched_points(
    found: dict[int, np.ndarray], placements: list[MarkerPlacement]
) -> tuple[np.ndarray, np.ndarray, int]:
    """Camera and projector corner arrays for the placed markers that were found.

    Ids that aren't part of the pattern (stray markers in the room) are ignored.

    Raises:
        CalibrationError: If too few of the pattern's markers were found.
    """
    matched = [placement for placement in placements if placement.id in found]
    if not matched:
        raise CalibrationError(NO_MARKERS_MESSAGE)
    if len(matched) < MIN_MARKERS:
        seen = [placement.id for placement in matched]
        raise CalibrationError(
            f"only {len(matched)} of {len(placements)} calibration markers visible (ids {seen}); "
            f"need {MIN_MARKERS}. Aim the camera so the whole projection is in view."
        )
    camera_points = np.vstack([found[placement.id] for placement in matched])
    projector_points = np.vstack([placement.corners() for placement in matched])
    return camera_points, projector_points, len(matched)


def solve_calibration(
    frame: np.ndarray, projector_size: tuple[int, int] = PROJECTOR_SIZE
) -> Calibration:
    """Fit the camera-to-projector homography from one frame of the projected pattern.

    Every corner of every detected marker is a point pair, so 6 markers give 24.

    Returns:
        A Calibration with no board fit, and its mean inlier error in projector px.

    Raises:
        CalibrationError: If too few markers are visible or no homography fits.
    """
    placements = marker_placements(projector_size)
    camera_points, projector_points, marker_count = _matched_points(
        detect_markers(frame), placements
    )
    homography, inlier_mask = cv2.findHomography(
        camera_points, projector_points, cv2.RANSAC, RANSAC_THRESHOLD_PX
    )
    if homography is None:
        raise CalibrationError("markers were found but no homography fits them; try again")
    inliers = inlier_mask.ravel().astype(bool)
    projected = cv2.perspectiveTransform(camera_points[inliers].reshape(-1, 1, 2), homography)
    errors = np.linalg.norm(projected.reshape(-1, 2) - projector_points[inliers], axis=1)
    frame_height, frame_width = frame.shape[:2]
    return Calibration(
        homography=homography,
        camera_size=(frame_width, frame_height),
        projector_size=projector_size,
        reprojection_error_px=float(errors.mean()),
        marker_count=marker_count,
        created_at=datetime.now(UTC).isoformat(timespec="seconds"),
    )


async def calibrate(
    camera: FreshFrameSource,
    show_pattern: Callable[[], Awaitable[None]],
    clear_pattern: Callable[[], Awaitable[None]],
    projector_size: tuple[int, int] = PROJECTOR_SIZE,
) -> Calibration:
    """Show the pattern, solve from a fresh frame, and always clear the pattern again.

    Args:
        camera: Frame source (Camera).
        show_pattern: Puts the board page into pattern mode (pattern_layout()).
        clear_pattern: Returns the page to normal mode. Runs even on failure.
            Hold the capture rig's lock around this call, so no clean capture
            restores the page while the pattern is up.
        projector_size: Stage size the pattern was laid out for.

    Raises:
        CalibrationError: If no attempted frame shows enough markers.
        CameraError: If the camera stops delivering frames.
    """
    try:
        await show_pattern()
        await asyncio.sleep(PATTERN_SETTLE_S)
        last_error = CalibrationError(NO_MARKERS_MESSAGE)
        for attempt in range(1, DETECT_ATTEMPTS + 1):
            frame = await asyncio.to_thread(camera.read_fresh)
            try:
                return solve_calibration(frame, projector_size)
            except CalibrationError as error:
                logger.info("calibration attempt %d failed: %s", attempt, error)
                last_error = error
        raise last_error
    finally:
        await clear_pattern()
