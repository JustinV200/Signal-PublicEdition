"""Fitting the projection to the physical whiteboard.

`detect_board_quad` finds the board's outline in a camera frame (best taken in
blank mode, so projected light doesn't blur the outline), among the bright
regions inside the projected area. `fit_board` maps it into
projector space with the calibration homography and picks a logical board size,
so the page can warp its stage onto the board and rectify.py can warp camera
frames into the same board view.
"""

from dataclasses import replace

import cv2
import numpy as np

from whiteboard.camera.calibration.record import Calibration
from whiteboard.camera.calibration.rectify import rectangle_corners

BLUR_KERNEL_PX = 7
# A region whose outline comes this close to the frame edge is cut off by the frame.
BORDER_MARGIN_PX = 2
# The board must cover a sane share of the frame: smaller is likely a sheet of
# paper or a light, and nearly all of it means the outline is out of view.
MIN_AREA_RATIO = 0.10
MAX_AREA_RATIO = 0.98
# The bright region must fill most of its quad, or it isn't rectangular.
MIN_FILL_RATIO = 0.85
# approxPolyDP tolerances tried in turn, as fractions of the outline's perimeter.
EPSILON_FRACTIONS = (0.02, 0.04, 0.06, 0.08)


def order_corners(points: np.ndarray) -> np.ndarray:
    """Order 4 points as top-left, top-right, bottom-right, bottom-left (float32 (4, 2)).

    TL has the smallest x+y and BR the largest; TR has the smallest y-x and BL the
    largest. Holds for any board tilted less than 45 degrees.
    """
    points = points.reshape(4, 2).astype(np.float32)
    sums = points.sum(axis=1)
    diffs = points[:, 1] - points[:, 0]
    return points[[np.argmin(sums), np.argmin(diffs), np.argmax(sums), np.argmax(diffs)]]


def _approximate_quad(outline: np.ndarray) -> np.ndarray | None:
    """Simplify a closed outline to 4 points, loosening the tolerance until it fits."""
    perimeter = cv2.arcLength(outline, True)
    for fraction in EPSILON_FRACTIONS:
        polygon = cv2.approxPolyDP(outline, fraction * perimeter, True)
        if len(polygon) == 4:
            return polygon
        if len(polygon) < 4:
            return None
    return None


def projected_area_in_camera(calibration: Calibration) -> np.ndarray:
    """The projector stage's outline in camera px (inverse homography), float32 (4, 2), TL first."""
    stage = rectangle_corners(calibration.projector_size).reshape(-1, 1, 2)
    return cv2.perspectiveTransform(stage, np.linalg.inv(calibration.homography)).reshape(4, 2)


def detect_board_quad(frame: np.ndarray, calibration: Calibration) -> np.ndarray | None:
    """Find the whiteboard: the bright, roughly rectangular region matching the projection.

    A white wall can be brighter and bigger than the board, so a region only counts
    if its centre is inside the projected area and it doesn't touch the frame edge.
    Of those, the one overlapping the projected area best (IoU) wins.

    Args:
        frame: Camera frame, BGR or grayscale, the size the calibration was solved on.
        calibration: Marker calibration; its homography locates the projected area.

    Returns:
        The corners in camera px, float32 (4, 2), ordered TL, TR, BR, BL, or None
        if no region qualifies (the caller keeps any existing fit).
    """
    gray = frame if frame.ndim == 2 else cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (BLUR_KERNEL_PX, BLUR_KERNEL_PX), 0)
    # Otsu splits bright board from darker wall without a hand-tuned level.
    _, bright = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    # CCOMP, not EXTERNAL: a board framed by dark trim inside a bright wall sits in a
    # hole of the wall's region, and EXTERNAL never returns regions inside holes.
    contours, hierarchy = cv2.findContours(bright, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
    if hierarchy is None:
        return None
    projected = projected_area_in_camera(calibration)
    # hierarchy rows are [next, previous, first child, parent]; no parent = an outer boundary.
    links = zip(contours, hierarchy[0], strict=True)
    outlines = [outline for outline, (_, _, _, parent) in links if parent < 0]
    candidates = [_board_candidate(outline, gray.shape, projected) for outline in outlines]
    quads = [quad for quad in candidates if quad is not None]
    if not quads:
        return None
    return max(quads, key=lambda quad: _overlap_ratio(quad, projected))


def _board_candidate(
    outline: np.ndarray, frame_shape: tuple[int, ...], projected: np.ndarray
) -> np.ndarray | None:
    """The ordered quad for one bright region, or None if it can't be the board."""
    x, y, width, height = cv2.boundingRect(outline)
    frame_height, frame_width = frame_shape[:2]
    # A region cut off by the frame edge (usually the wall) isn't fully in view.
    if min(x, y) < BORDER_MARGIN_PX:
        return None
    if x + width > frame_width - BORDER_MARGIN_PX or y + height > frame_height - BORDER_MARGIN_PX:
        return None
    # The hull closes notches where ink or the marker tray touches the board edge.
    quad = _approximate_quad(cv2.convexHull(outline))
    if quad is None or not cv2.isContourConvex(quad):
        return None
    quad_area = cv2.contourArea(quad)
    if not MIN_AREA_RATIO <= quad_area / (frame_width * frame_height) <= MAX_AREA_RATIO:
        return None
    if cv2.contourArea(outline) / quad_area < MIN_FILL_RATIO:
        return None
    ordered = order_corners(quad)
    centre_x, centre_y = ordered.mean(axis=0)
    if cv2.pointPolygonTest(projected, (float(centre_x), float(centre_y)), False) < 0:
        return None
    return ordered


def _overlap_ratio(quad: np.ndarray, projected: np.ndarray) -> float:
    """Intersection over union of two convex quads (float32 (4, 2))."""
    intersection, _ = cv2.intersectConvexConvex(quad, projected)
    union = cv2.contourArea(quad) + cv2.contourArea(projected) - intersection
    return float(intersection / union)


def board_quad_in_projector(quad_camera: np.ndarray, homography: np.ndarray) -> np.ndarray:
    """Map board corners from camera px to projector px through the calibration homography.

    Returns:
        float32 (4, 2), same corner order as the input.
    """
    points = quad_camera.reshape(-1, 1, 2).astype(np.float32)
    return cv2.perspectiveTransform(points, homography).reshape(4, 2)


def board_quad_in_camera(quad_projector: np.ndarray, homography: np.ndarray) -> np.ndarray:
    """Map board corners from projector px back to camera px (the inverse of the above).

    Gives where the camera should see the board if the current fit is still right.

    Returns:
        float32 (4, 2), same corner order as the input.
    """
    return board_quad_in_projector(quad_projector, np.linalg.inv(homography))


def board_view_size(quad_projector: np.ndarray, height: int) -> tuple[int, int]:
    """Logical board size: `height` tall, as wide as the board's aspect ratio allows.

    The aspect is measured in projector px, which are close to square on the board
    when the projector faces it roughly head-on.
    """
    top_left, top_right, bottom_right, bottom_left = quad_projector.reshape(4, 2)
    distance = np.linalg.norm
    width_px = (distance(top_right - top_left) + distance(bottom_right - bottom_left)) / 2
    height_px = (distance(bottom_left - top_left) + distance(bottom_right - top_right)) / 2
    return round(height * width_px / height_px), height


def fit_board(calibration: Calibration, quad_camera: np.ndarray, height: int) -> Calibration:
    """A copy of `calibration` with the board fitted (board_quad and board_size set).

    Args:
        calibration: Marker calibration solved for the current camera position.
        quad_camera: Board corners from detect_board_quad.
        height: Logical board height ([display] fit_height).
    """
    quad_projector = board_quad_in_projector(quad_camera, calibration.homography)
    return replace(
        calibration,
        board_quad=quad_projector,
        board_size=board_view_size(quad_projector, height),
    )
