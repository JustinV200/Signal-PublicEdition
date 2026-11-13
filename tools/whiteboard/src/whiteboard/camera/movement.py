"""Telling what moved: the projector (a fresh homography) or the camera (two blank photos).

A new marker solve changes H whether the projector or the camera moved, so H
alone can't say which. A camera move shifts the whole room in the frame; a
projector move doesn't show in a blank-page photo at all. So the re-align keeps
a blank photo from the last time the alignment was confirmed (ReferencePhoto,
on disk so a restart keeps it) and compares the next one with it.
"""

import json
import logging
import math
from pathlib import Path

import cv2
import numpy as np

from whiteboard.camera.calibration import Calibration, board_quad_in_camera
from whiteboard.camera.drift import corner_error

logger = logging.getLogger(__name__)

# Phase correlation runs on quarter-size frames: fast, and sensor noise averages out.
SHIFT_SCALE = 0.25
# Tile sides are rounded down to this: OpenCV pads odd DFT sizes, which biases the
# result by half a pixel.
TILE_MULTIPLE_PX = 8


def homography_drift_px(
    old_homography: np.ndarray, new_homography: np.ndarray, projector_size: tuple[int, int]
) -> float:
    """How far the projector's corners moved in the camera between two solves (mean, camera px)."""
    width, height = projector_size
    corners = np.array([[0, 0], [width, 0], [width, height], [0, height]], np.float32)
    return corner_error(
        board_quad_in_camera(corners, old_homography), board_quad_in_camera(corners, new_homography)
    )


def camera_shift_px(reference: np.ndarray, frame: np.ndarray) -> float | None:
    """How far the scene moved between two blank camera frames, in camera px.

    Phase correlation finds the shift that best lines up each quarter of the
    frame; the largest one is returned. One global shift would miss a roll or a
    zoom (they shift the quarters in different directions). Ink drawn in between
    barely matters, because the wall, door and board edges dominate.

    Returns:
        The largest quarter's shift, or None when the frames' sizes differ.
    """
    if reference.shape != frame.shape:
        return None
    first, second = _prepared(reference), _prepared(frame)
    height, width = first.shape
    tile_height = height // 2 // TILE_MULTIPLE_PX * TILE_MULTIPLE_PX
    tile_width = width // 2 // TILE_MULTIPLE_PX * TILE_MULTIPLE_PX
    window = cv2.createHanningWindow((tile_width, tile_height), cv2.CV_32F)
    shifts = []
    for top in (0, height - tile_height):
        for left in (0, width - tile_width):
            tiles = (
                image[top : top + tile_height, left : left + tile_width]
                for image in (first, second)
            )
            (shift_x, shift_y), _response = cv2.phaseCorrelate(*tiles, window)
            shifts.append(math.hypot(shift_x, shift_y))
    return max(shifts) / SHIFT_SCALE


def _prepared(frame: np.ndarray) -> np.ndarray:
    """Grey, quarter size, float32: what phaseCorrelate wants."""
    gray = frame if frame.ndim == 2 else cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    small = cv2.resize(gray, None, fx=SHIFT_SCALE, fy=SHIFT_SCALE, interpolation=cv2.INTER_AREA)
    return small.astype(np.float32)


class ReferencePhoto:
    """A blank-page camera frame from when the marker calibration was last confirmed.

    Tagged with that calibration's created_at, so after a new calibration the old
    photo no longer counts. Callers write it only when a calibration is new (a
    deliberate calibrate, a re-align, or the first check that confirms one), never
    to refresh it: a camera creeping a little at a time would drag it along.
    """

    def __init__(self, png_path: Path) -> None:
        """Args: png_path: Where the photo lives; its tag goes next to it as .json."""
        self._png_path = png_path
        self._tag_path = png_path.with_suffix(".json")

    def load(self, marker: Calibration) -> np.ndarray | None:
        """The photo if it was taken under `marker`, else None (missing, stale or unreadable)."""
        try:
            tag = json.loads(self._tag_path.read_text(encoding="utf-8"))["created_at"]
        except (OSError, ValueError, KeyError, TypeError):
            return None
        if tag != marker.created_at:
            return None
        return cv2.imread(str(self._png_path))

    def save(self, frame: np.ndarray, marker: Calibration) -> None:
        """Keep `frame` as the photo for `marker`. A failed write is logged, not raised:
        without the photo, the re-align only refuses carry-overs it can't check."""
        try:
            self._png_path.parent.mkdir(parents=True, exist_ok=True)
            if not cv2.imwrite(str(self._png_path), frame):
                raise OSError(f"couldn't write {self._png_path}")
            tag = json.dumps({"created_at": marker.created_at})
            self._tag_path.write_text(tag, encoding="utf-8")
        except OSError as error:
            logger.warning("couldn't keep the alignment reference photo: %s", error)
