"""The cross-out check's deterministic steps, free of the camera and the model.

StrikeWatcher (strike_watch.py) runs these around the model check (strike_confirm.py):
reading the two snapshots, whether they're in board px, whether the change erased
ink near the rows (old ink a camera bump shifted, not a cross-out), whether all the
change stays inside the crossed-out rows, and which confirmed rows only get a hint
because the row next to them reads the same.
"""

from collections.abc import Sequence
from dataclasses import replace
from pathlib import Path

import cv2
import numpy as np

from whiteboard.camera import BORDER_NOISE_PX, BBox
from whiteboard.daemon.todo.strike_confirm import StrikeVerdict
from whiteboard.todo import StrikeTarget

# A snapshot may differ from the board size by rounding; more means it isn't in board px.
SIZE_TOLERANCE_PX = 2
# Ink this far outside the crossed-out rows' boxes is other writing the agent should see.
# The boxes span the whole column, so a cross-out running on past the text stays inside.
OUTSIDE_SLACK_PX = 12
# A cross-out erases nothing (0 px in the sims, with up to 2 px of camera wobble). The
# smallest old stroke a shift can turn into a candidate (2 em of a short item, thin
# marker) erases about 140 px where it was. Before the noise gate (camera.detection
# NOISE_K), quiet pairs of real snapshots erased up to about 85 px of noise near the
# rows; with it, six quiet lit pairs erase 0 px away from the border strip, so 100
# keeps them under. One dim pair (snapshot medians 33-40) still erases 630 px with the
# gate, outside the border strip: 598 px along the bottom just above it (y 669-702,
# where a bright strip of text at the frame's bottom edge changed) and a 32 px blob at
# y 536. When the open rows come within a row of that bottom band, a real cross-out
# reads as a shift and goes to the agent unticked.
SHIFT_ERASED_FLOOR_PX = 100
# Old ink that shifted adds and erases about as much: with at least this many erased
# pixels per added pixel near the rows, it's a shift.
SHIFT_ERASED_RATIO = 0.5
# Old ink a bump moves onto a row was at most [align] drift_px (15) away, or the drift
# check stops it first. That's under half a row only for rows of 30 px or more; for
# smaller fonts it's more, but still within this one-row reach.
SHIFT_REACH_ROWS = 1.0


def read_pair(before: Path, after: Path) -> tuple[np.ndarray, np.ndarray] | None:
    """Both snapshots as BGR arrays of one size, or None if either can't be read."""
    images = [_read_bgr(path) for path in (before, after)]
    if any(image is None for image in images) or images[0].shape != images[1].shape:
        return None
    return images[0], images[1]


def _read_bgr(path: Path) -> np.ndarray | None:
    """Decode a PNG snapshot, or None if it's missing or unreadable."""
    try:
        return cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_COLOR)
    except OSError:
        return None


def is_board_sized(image: np.ndarray, board_size: tuple[float, float]) -> bool:
    """Whether a snapshot is in board pixels (calibrated and fitted), like the rows.

    Args:
        image: The snapshot.
        board_size: The board's (width, height) the rows are laid out in.
    """
    width, height = board_size
    image_h, image_w = image.shape[:2]
    return abs(image_w - width) <= SIZE_TOLERANCE_PX and abs(image_h - height) <= SIZE_TOLERANCE_PX


def looks_shifted(added: np.ndarray, erased: np.ndarray, rows: Sequence[StrikeTarget]) -> bool:
    """Whether ink was erased near the rows too, so the change isn't a pure cross-out.

    Most likely old ink a camera bump shifted onto an open row. Only ink within
    SHIFT_REACH_ROWS of the rows, and away from the image's flickering border, is
    weighed: erasing at least SHIFT_ERASED_FLOOR_PX there, or SHIFT_ERASED_RATIO of
    what was added there, counts. The floor is what catches a bump that slides the
    board's dark frame into view beside the rows: the frame adds thousands of px,
    which drowns the ratio. A real cross-out made together with a wipe near the rows
    counts too, so it goes to the agent and nothing is ticked.

    Args:
        added, erased: The change's masks (camera.added_and_erased_ink), in board px.
        rows: The open rows the change is matched against (not empty).
    """
    area = _shift_area(rows, erased.shape)
    erased_px = np.count_nonzero(erased[area])
    return erased_px >= SHIFT_ERASED_FLOOR_PX or (
        erased_px >= SHIFT_ERASED_RATIO * np.count_nonzero(added[area])
    )


def _shift_area(rows: Sequence[StrikeTarget], shape: tuple[int, ...]) -> tuple[slice, slice]:
    """(y, x) slices around the rows, SHIFT_REACH_ROWS wider, inside BORDER_NOISE_PX."""
    height, width = shape[:2]
    reach = SHIFT_REACH_ROWS * max(row.y1 - row.y0 for row in rows)
    left, top, right, bottom = _rows_box(rows, reach)
    return (
        slice(max(BORDER_NOISE_PX, round(top)), min(height - BORDER_NOISE_PX, round(bottom))),
        slice(max(BORDER_NOISE_PX, round(left)), min(width - BORDER_NOISE_PX, round(right))),
    )


def is_inside(changed_bbox: BBox, strikes: Sequence[StrikeTarget]) -> bool:
    """Whether the changed ink stays within the crossed-out rows' boxes (plus a little)."""
    x, y, w, h = changed_bbox
    left, top, right, bottom = _rows_box(strikes, OUTSIDE_SLACK_PX)
    return x >= left and y >= top and x + w <= right and y + h <= bottom


def _rows_box(rows: Sequence[StrikeTarget], slack: float) -> tuple[float, float, float, float]:
    """(left, top, right, bottom) around the rows' whole boxes, `slack` px wider on each side."""
    return (
        min(row.row_x0 for row in rows) - slack,
        min(row.y0 for row in rows) - slack,
        max(row.row_x1 for row in rows) + slack,
        max(row.y1 for row in rows) + slack,
    )


def demote_twins(verdict: StrikeVerdict, candidates: Sequence[StrikeTarget]) -> StrikeVerdict:
    """`verdict` with every struck row that has a twin (StrikeTarget.has_twin) made unsure.

    The calibration can be off by most of a row, and then a line through one of two
    same-worded rows looks like a line through the other's words too, so neither the
    geometry nor the model can say which was meant. A hint is cheap; a wrong tick isn't.
    """
    twins = {candidate.id for candidate in candidates if candidate.has_twin}
    struck = tuple(item for item in verdict.struck if item not in twins)
    demoted = tuple(item for item in verdict.struck if item in twins)
    return replace(verdict, struck=struck, unsure=(*verdict.unsure, *demoted))
