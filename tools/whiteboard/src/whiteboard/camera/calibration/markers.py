"""The calibration pattern: ArUco markers and where they sit in projector space.

The daemon serves `pattern_layout()` to the board page's pattern mode, which
draws each PNG at its (x, y) at its size on the black stage. solve.py matches the
detected marker corners against `MarkerPlacement.corners()` to fit the homography.
"""

from dataclasses import dataclass

import cv2
import numpy as np

ARUCO_DICTIONARY = cv2.aruco.DICT_4X4_50
PROJECTOR_SIZE: tuple[int, int] = (1280, 720)

# A 4x4 marker is 6 cells across: 4 data cells plus a 1-cell black border.
MARKER_CELLS = 6
# White margin around each marker, in cells. The page background is black, so
# without it the marker's black border would merge into the background and the
# detector could not find the marker's outline.
QUIET_CELLS = 1
CELL_PX = 18
MARKER_PX = MARKER_CELLS * CELL_PX
QUIET_PX = QUIET_CELLS * CELL_PX
TILE_PX = MARKER_PX + 2 * QUIET_PX
# Gap between a tile and the stage edge. Projected edges are often soft or cut off.
EDGE_INSET_PX = 40
WHITE = 255


@dataclass(frozen=True)
class MarkerPlacement:
    """One marker tile on the stage: its id, top-left corner and side, in projector px."""

    id: int
    x: int
    y: int
    size: int

    def corners(self) -> np.ndarray:
        """The marker's own black square (inside the white margin), as float32 (4, 2).

        Ordered top-left, top-right, bottom-right, bottom-left, the order ArUco
        reports detected corners in.
        """
        left, top = self.x + QUIET_PX, self.y + QUIET_PX
        right, bottom = left + MARKER_PX, top + MARKER_PX
        return np.array([[left, top], [right, top], [right, bottom], [left, bottom]], np.float32)


def aruco_dictionary() -> cv2.aruco.Dictionary:
    """The ArUco dictionary the pattern is drawn from and detected with."""
    return cv2.aruco.getPredefinedDictionary(ARUCO_DICTIONARY)


def marker_placements(projector_size: tuple[int, int] = PROJECTOR_SIZE) -> list[MarkerPlacement]:
    """Six tiles: three along the top edge and three along the bottom, inset from the edges.

    Spreading points to the corners keeps the homography accurate across the
    whole stage, not just near the markers.

    Raises:
        ValueError: If the stage is too small to fit the tiles.
    """
    width, height = projector_size
    left, right = EDGE_INSET_PX, width - EDGE_INSET_PX - TILE_PX
    top, bottom = EDGE_INSET_PX, height - EDGE_INSET_PX - TILE_PX
    if right <= left + TILE_PX or bottom <= top + TILE_PX:
        raise ValueError(f"projector size {projector_size} is too small for the marker pattern")
    columns = (left, (width - TILE_PX) // 2, right)
    positions = [(x, top) for x in columns] + [(x, bottom) for x in columns]
    return [MarkerPlacement(i, x, y, TILE_PX) for i, (x, y) in enumerate(positions)]


def render_tile(marker_id: int) -> np.ndarray:
    """One marker with its white margin, as a TILE_PX square grayscale image."""
    marker = cv2.aruco.generateImageMarker(aruco_dictionary(), marker_id, MARKER_PX)
    return cv2.copyMakeBorder(
        marker, QUIET_PX, QUIET_PX, QUIET_PX, QUIET_PX, cv2.BORDER_CONSTANT, value=WHITE
    )


def pattern_layout(projector_size: tuple[int, int] = PROJECTOR_SIZE) -> list[dict]:
    """The pattern for the board page: one entry per marker tile.

    Returns:
        A list of {id, x, y, size, png_bytes}: the tile's top-left corner and side
        in projector px, and the tile image as PNG. The page should draw it at
        exactly that size with `image-rendering: pixelated`.

    Raises:
        ValueError: If the stage is too small (see marker_placements).
        RuntimeError: If OpenCV can't encode a tile.
    """
    layout = []
    for placement in marker_placements(projector_size):
        is_ok, png = cv2.imencode(".png", render_tile(placement.id))
        if not is_ok:
            raise RuntimeError(f"could not encode marker {placement.id} as PNG")
        layout.append(
            {
                "id": placement.id,
                "x": placement.x,
                "y": placement.y,
                "size": placement.size,
                "png_bytes": png.tobytes(),
            }
        )
    return layout
