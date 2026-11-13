"""Saving board snapshots as PNGs in .state/snapshots/ and pruning old ones.

clean_capture.py saves each clean capture here, and the change watcher saves
the capture it reports. Names sort by time, so pruning keeps the newest.
"""

from datetime import datetime, timedelta
from pathlib import Path

import cv2
import numpy as np

SNAPSHOT_PREFIX = "snapshot-"


def save_snapshot(image: np.ndarray, snapshot_dir: Path, keep: int) -> Path:
    """Write `image` as a timestamped PNG, then delete all but the newest `keep`.

    Returns:
        The new PNG's path.

    Raises:
        ValueError: If keep is below 1 (the new snapshot would be deleted).
        OSError: If the PNG can't be encoded or written.
    """
    if keep < 1:
        raise ValueError(f"keep must be at least 1, got {keep}")
    is_ok, png = cv2.imencode(".png", image)
    if not is_ok:
        raise OSError("could not encode snapshot as PNG")
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    path = _write_new_file(snapshot_dir, png.tobytes())
    for old_path in sorted(snapshot_dir.glob(f"{SNAPSHOT_PREFIX}*.png"))[:-keep]:
        old_path.unlink(missing_ok=True)
    return path


def _write_new_file(snapshot_dir: Path, data: bytes) -> Path:
    """Write `data` to a new, never-overwritten file named by the current time.

    The Windows clock can tick coarser than a microsecond, so two quick captures may
    get the same time. Exclusive create catches that, and the name moves on by a
    microsecond, which keeps names unique and still sorted by time. Writing the
    bytes ourselves also avoids cv2.imwrite, which fails on non-ASCII Windows paths.
    """
    moment = datetime.now()
    while True:
        path = snapshot_dir / f"{SNAPSHOT_PREFIX}{moment:%Y%m%d-%H%M%S-%f}.png"
        try:
            with path.open("xb") as snapshot_file:
                snapshot_file.write(data)
            return path
        except FileExistsError:
            moment += timedelta(microseconds=1)
