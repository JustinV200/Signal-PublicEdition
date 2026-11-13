"""The calibration record and its calibration.json file.

A `Calibration` holds the camera-to-projector homography from the marker
pattern (solve.py) and, once the board is fitted (board.py), the whiteboard's
corners in projector space and the logical board size. rectify.py turns it into
the warp that produces `board_look` images.
"""

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from whiteboard.shared import write_atomically


class CalibrationError(RuntimeError):
    """Calibration failed, or calibration.json is unreadable or invalid."""


@dataclass(frozen=True, eq=False)
class Calibration:
    """How camera pixels map onto the projector stage and the board.

    Attributes:
        homography: 3x3 float64 matrix from camera px to projector px.
        camera_size: (width, height) of the camera frames it was solved on.
        projector_size: (width, height) of the projector stage.
        reprojection_error_px: Mean marker-corner error after the fit, in projector px.
        marker_count: How many markers the fit used.
        created_at: ISO 8601 UTC timestamp.
        board_quad: The board's corners in projector px, float32 (4, 2) ordered
            TL, TR, BR, BL; None until the board is fitted.
        board_size: (width, height) of the logical board view; None until fitted.
    """

    homography: np.ndarray
    camera_size: tuple[int, int]
    projector_size: tuple[int, int]
    reprojection_error_px: float
    marker_count: int
    created_at: str
    board_quad: np.ndarray | None = None
    board_size: tuple[int, int] | None = None


def save_calibration(calibration: Calibration, path: Path) -> None:
    """Write calibration.json atomically (temp file, then rename).

    Raises:
        OSError: If the file can't be written.
    """
    data = {
        "homography": calibration.homography.tolist(),
        "camera_size": list(calibration.camera_size),
        "projector_size": list(calibration.projector_size),
        "reprojection_error_px": calibration.reprojection_error_px,
        "marker_count": calibration.marker_count,
        "created_at": calibration.created_at,
        "board_quad": None if calibration.board_quad is None else calibration.board_quad.tolist(),
        "board_size": None if calibration.board_size is None else list(calibration.board_size),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    write_atomically(path, json.dumps(data, indent=2).encode("utf-8"))


def load_calibration(path: Path) -> Calibration | None:
    """Read calibration.json. Returns None if the file doesn't exist.

    Raises:
        CalibrationError: If the file exists but isn't a valid calibration.
    """
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        board_quad = data.get("board_quad")
        board_size = data.get("board_size")
        return Calibration(
            homography=_finite_array(data["homography"], (3, 3), np.float64),
            camera_size=_size(data["camera_size"]),
            projector_size=_size(data["projector_size"]),
            reprojection_error_px=float(data["reprojection_error_px"]),
            marker_count=int(data["marker_count"]),
            created_at=str(data["created_at"]),
            board_quad=None if board_quad is None else _finite_array(board_quad, (4, 2)),
            board_size=None if board_size is None else _size(board_size),
        )
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise CalibrationError(f"{path} is not a valid calibration: {error}") from error


def _finite_array(value: object, shape: tuple[int, ...], dtype: type = np.float32) -> np.ndarray:
    """A numeric array of exactly `shape` with no NaN or inf, else ValueError."""
    array = np.asarray(value, dtype=dtype)
    if array.shape != shape or not np.isfinite(array).all():
        raise ValueError(f"expected a finite {shape} array, got {value!r}")
    return array


def _size(value: object) -> tuple[int, int]:
    """A (width, height) pair of positive ints, else ValueError."""
    width, height = (int(part) for part in value)  # type: ignore[union-attr]
    if width <= 0 or height <= 0:
        raise ValueError(f"expected a positive (width, height), got {value!r}")
    return width, height
