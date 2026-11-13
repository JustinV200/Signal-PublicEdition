"""BoardChange: one "the owner's ink changed" event, and how two of them coalesce.

The change watcher reports these; the board agent keeps at most one pending
change and merges any that arrive while a turn is running.
"""

from dataclasses import dataclass
from pathlib import Path

BoundingBox = tuple[int, int, int, int]
"""(x, y, w, h) in board coordinates."""


@dataclass(frozen=True)
class BoardChange:
    """The board's ink changed.

    Attributes:
        png_path: The clean snapshot taken after the change.
        changed_bbox: Where the ink changed, or None if unknown.
        before_path: The previous clean snapshot, for before/after comparison, if any.
    """

    png_path: Path
    changed_bbox: BoundingBox | None
    before_path: Path | None = None


def merge_changes(older: BoardChange | None, newer: BoardChange) -> BoardChange:
    """Coalesce a pending change with a newer one into a single turn's worth.

    Args:
        older: The change still waiting for a turn, if any.
        newer: The change that just arrived.

    Returns:
        The newer snapshot, with a box covering both changed regions. An
        unknown region on either side makes the merged region unknown.
    """
    if older is None:
        return newer
    # The merged change starts where the oldest one did, so it keeps that "before".
    bbox = union_bbox(older.changed_bbox, newer.changed_bbox)
    return BoardChange(newer.png_path, bbox, older.before_path)


def union_bbox(first: BoundingBox | None, second: BoundingBox | None) -> BoundingBox | None:
    """Return the smallest box covering both, or None if either is unknown."""
    if first is None or second is None:
        return None
    left = min(first[0], second[0])
    top = min(first[1], second[1])
    right = max(first[0] + first[2], second[0] + second[2])
    bottom = max(first[1] + first[3], second[1] + second[3])
    return (left, top, right - left, bottom - top)
