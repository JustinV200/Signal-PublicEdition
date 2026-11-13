"""Tests for the board-fit math: the stage corners must land exactly on the quad corners."""

import numpy as np
import pytest

from whiteboard.display.scene import (
    SceneError,
    css_matrix3d,
    logical_size,
    parse_quad,
    stage_homography,
)

# A keystoned board: wider at the bottom, slightly rotated.
QUAD = parse_quad([[150, 80], [1130, 60], [1220, 690], [70, 700]])


def _apply_css_matrix3d(values: list[float], x: float, y: float) -> tuple[float, float]:
    # CSS matrix3d is column-major; transform the point (x, y, 0, 1) and divide by w.
    matrix = np.array(values).reshape(4, 4).T
    out = matrix @ np.array([x, y, 0.0, 1.0])
    return out[0] / out[3], out[1] / out[3]


def test_matrix3d_maps_stage_corners_onto_quad() -> None:
    width, height = logical_size(QUAD, 720)
    values = css_matrix3d(stage_homography(QUAD, (width, height)))
    stage_corners = [(0, 0), (width, 0), (width, height), (0, height)]
    for (x, y), expected in zip(stage_corners, QUAD, strict=True):
        assert _apply_css_matrix3d(values, x, y) == pytest.approx(expected, abs=1e-6)


def test_logical_size_follows_board_aspect() -> None:
    square = parse_quad([[100, 100], [500, 100], [500, 500], [100, 500]])
    assert logical_size(square, 720) == (720, 720)


@pytest.mark.parametrize(
    "raw",
    [
        [[0, 0], [10, 0], [10, 10]],  # too few corners
        [[0, 0], [0, 10], [10, 10], [10, 0]],  # counter-clockwise
        [[0, 0], [10, 10], [10, 0], [0, 10]],  # self-intersecting
        [[0, 0], [5, 0], [10, 0], [0, 10]],  # three collinear corners
    ],
)
def test_bad_quads_are_rejected(raw: list) -> None:
    with pytest.raises(SceneError):
        parse_quad(raw)
