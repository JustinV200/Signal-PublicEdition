"""Board fit (software keystone): map the logical stage onto the board's corners on the projector.

The owner gives the 4 projector-pixel points where the physical board's corners
land (TL, TR, BR, BL). The logical stage takes the board's aspect ratio, and the
page warps it onto that quad with a CSS `matrix3d` built from the homography
below. Everything outside the quad stays black, so no light spills on the wall.
"""

import math
from typing import Any

import numpy as np

from whiteboard.display.scene.fields import require_number
from whiteboard.display.scene.model import Point, Quad, SceneError

QUAD_CORNERS = 4


def parse_quad(raw: Any) -> Quad:
    """Validate a board quad from JSON: 4 [x, y] points, clockwise from the top-left, convex.

    Args:
        raw: A list of 4 two-number lists, in projector pixels.

    Returns:
        The quad as a tuple of (x, y) tuples.

    Raises:
        SceneError: If the shape, numbers, order or convexity is wrong.
    """
    if not isinstance(raw, list | tuple) or len(raw) != QUAD_CORNERS:
        raise SceneError("quad must be a list of 4 [x, y] points (TL, TR, BR, BL)")
    points: list[Point] = []
    for position, point in enumerate(raw):
        if not isinstance(point, list | tuple) or len(point) != 2:
            raise SceneError(f"quad[{position}] must be an [x, y] pair")
        points.append(
            (
                require_number(point[0], f"quad[{position}].x"),
                require_number(point[1], f"quad[{position}].y"),
            )
        )
    quad: Quad = (points[0], points[1], points[2], points[3])
    if not _is_clockwise_convex(quad):
        raise SceneError("quad corners must be TL, TR, BR, BL (clockwise) and form a convex shape")
    return quad


def logical_size(quad: Quad, height: int) -> tuple[int, int]:
    """Size the logical stage to the board's aspect ratio, estimated from the quad's edges.

    Args:
        quad: The board corners in projector pixels.
        height: The logical stage height to use.

    Returns:
        (width, height) in logical pixels.
    """
    top_left, top_right, bottom_right, bottom_left = quad
    horizontal = math.dist(top_left, top_right) + math.dist(bottom_left, bottom_right)
    vertical = math.dist(top_left, bottom_left) + math.dist(top_right, bottom_right)
    return round(height * horizontal / vertical), height


def stage_homography(quad: Quad, size: tuple[int, int]) -> np.ndarray:
    """Compute the 3x3 homography that maps the logical stage rectangle onto the quad.

    Stage (0,0), (w,0), (w,h), (0,h) land on quad TL, TR, BR, BL. Invert it to go
    from projector pixels back to board pixels (e.g. to warp camera frames).

    Args:
        quad: The board corners in projector pixels.
        size: The logical stage (width, height).

    Returns:
        A 3x3 float matrix H with H[2, 2] == 1, mapping [x, y, 1] to homogeneous projector pixels.

    Raises:
        SceneError: If the quad is degenerate and no homography exists.
    """
    width, height = size
    stage_corners = ((0.0, 0.0), (width, 0.0), (width, height), (0.0, height))
    rows: list[list[float]] = []
    targets: list[float] = []
    for (x, y), (u, v) in zip(stage_corners, quad, strict=True):
        rows.append([x, y, 1, 0, 0, 0, -u * x, -u * y])
        rows.append([0, 0, 0, x, y, 1, -v * x, -v * y])
        targets.extend((u, v))
    try:
        solution = np.linalg.solve(np.array(rows), np.array(targets))
    except np.linalg.LinAlgError as error:
        raise SceneError("quad is degenerate; no homography maps the stage onto it") from error
    return np.append(solution, 1.0).reshape(3, 3)


def css_matrix3d(homography: np.ndarray) -> list[float]:
    """Turn a 2D homography into the 16 column-major values of a CSS `matrix3d()`.

    The z row and column are identity, so the element stays flat while x/y get the
    perspective divide. The element needs `transform-origin: 0 0`.

    Args:
        homography: A 3x3 matrix from stage_homography.

    Returns:
        16 floats, ready for `matrix3d(${values.join(",")})`.
    """
    h = homography
    # Insert an identity z axis: row/column 2 of the 4x4 maps (x, y, z, w).
    matrix4 = np.array(
        [
            [h[0, 0], h[0, 1], 0.0, h[0, 2]],
            [h[1, 0], h[1, 1], 0.0, h[1, 2]],
            [0.0, 0.0, 1.0, 0.0],
            [h[2, 0], h[2, 1], 0.0, h[2, 2]],
        ]
    )
    # CSS matrix3d() lists the values column by column.
    return [float(value) for value in matrix4.T.flatten()]


def stage_geometry(
    quad: Quad | None, projector_size: tuple[int, int], fit_height: int
) -> dict[str, Any]:
    """Describe the stage for the page and /api/status: logical size plus the warp, if fitted.

    Args:
        quad: The board fit, or None for an unwarped stage the size of the projector.
        projector_size: Projector (width, height) in pixels.
        fit_height: Logical stage height to use when fitted.

    Returns:
        `{width, height, fitted, quad, matrix3d, projector: {width, height}}`.
    """
    projector = {"width": projector_size[0], "height": projector_size[1]}
    if quad is None:
        width, height = projector_size
        return {
            "width": width,
            "height": height,
            "fitted": False,
            "quad": None,
            "matrix3d": None,
            "projector": projector,
        }
    size = logical_size(quad, fit_height)
    return {
        "width": size[0],
        "height": size[1],
        "fitted": True,
        "quad": [list(point) for point in quad],
        "matrix3d": css_matrix3d(stage_homography(quad, size)),
        "projector": projector,
    }


def _is_clockwise_convex(quad: Quad) -> bool:
    # With y pointing down, a visually clockwise turn has a positive cross product.
    # All four turns positive means convex, non-degenerate and correctly ordered.
    for index in range(QUAD_CORNERS):
        ax, ay = quad[index]
        bx, by = quad[(index + 1) % QUAD_CORNERS]
        cx, cy = quad[(index + 2) % QUAD_CORNERS]
        if (bx - ax) * (cy - by) - (by - ay) * (cx - bx) <= 0:
            return False
    return True
