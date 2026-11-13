"""Crops for triage: the changed region before and after, plus a thumbnail of the whole board."""

from pathlib import Path

import cv2
import numpy as np

from whiteboard.agent.board_change import BoundingBox

# The changed box is grown by this fraction of its size on every side, for context.
PAD_FRACTION = 0.10
# The whole-board thumbnail is scaled to at most this wide.
THUMB_WIDTH_PX = 384


def padded_box(bbox: BoundingBox, width: int, height: int) -> tuple[int, int, int, int]:
    """Grow `bbox` by PAD_FRACTION per side, clamped to the image: (left, top, right, bottom)."""
    x, y, w, h = bbox
    pad_x, pad_y = round(w * PAD_FRACTION), round(h * PAD_FRACTION)
    return (
        max(0, x - pad_x),
        max(0, y - pad_y),
        min(width, x + w + pad_x),
        min(height, y + h + pad_y),
    )


def crop_before_after(
    before_path: Path, after_path: Path, bbox: BoundingBox
) -> tuple[bytes, bytes, bytes] | None:
    """PNG bytes of the padded region before and after, and a thumbnail of the whole "after".

    Returns:
        (before_crop, after_crop, thumbnail), or None when the crop can't be made (a
        snapshot is unreadable, the two differ in size, or the box is empty), so the
        caller falls back to judging the whole board.
    """
    before, after = _read(before_path), _read(after_path)
    if before is None or after is None or before.shape != after.shape:
        return None
    height, width = after.shape[:2]
    left, top, right, bottom = padded_box(bbox, width, height)
    if right <= left or bottom <= top:
        return None
    scale = min(1.0, THUMB_WIDTH_PX / width)
    thumb = cv2.resize(after, (round(width * scale), round(height * scale)))
    return (
        _png(before[top:bottom, left:right]),
        _png(after[top:bottom, left:right]),
        _png(thumb),
    )


def _read(path: Path) -> np.ndarray | None:
    """Decode a PNG, or None if it's missing or unreadable."""
    try:
        return cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_COLOR)
    except OSError:
        return None


def _png(image: np.ndarray) -> bytes:
    """Encode an image as PNG bytes."""
    return cv2.imencode(".png", image)[1].tobytes()
