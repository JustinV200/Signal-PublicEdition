"""Clean captures: read the owner's ink with the projection briefly turned off.

The board page goes all black for `blank_ms`, a fresh frame is grabbed, and the
page always goes back to normal mode, even if the grab fails. The frame is then
rectified into board space (or left raw if uncalibrated). POST /api/look and the
change watcher both capture through the daemon's one `CaptureRig`, whose lock
keeps one capture's restore from un-blanking the page during another's grab.
"""

import asyncio
import logging
import math
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import NamedTuple, Protocol

import numpy as np

from whiteboard.camera.calibration import Calibration, rectify_to_view
from whiteboard.camera.camera import STALE_FRAME_S
from whiteboard.camera.device import CameraError
from whiteboard.camera.snapshots import save_snapshot
from whiteboard.shared import FractionBox

logger = logging.getLogger(__name__)

# Display modes this package asks the board page for (see display/).
BLANK_MODE = "blank"
NORMAL_MODE = "normal"
STALE_CAMERA_MESSAGE = (
    f"the camera has sent no frames for over {STALE_FRAME_S:.0f} s "
    "(unplugged, or in use by another app?); not blanking the board"
)

SetMode = Callable[[str], Awaitable[None]]


class FrameSource(Protocol):
    """What clean captures and the watcher need from a camera (Camera has both).

    `latest()` returns None when there's no recent frame (the camera is stale).
    """

    def latest(self) -> np.ndarray | None: ...

    def read_fresh(self) -> np.ndarray: ...


@dataclass
class CaptureRig:
    """Everything a clean capture needs. The daemon owns one and shares it.

    Attributes:
        camera: The live frame source.
        set_mode: Async callable that pushes a display mode ("blank"/"normal") to the page.
        snapshot_dir: Where snapshots go (.state/snapshots).
        blank_ms: How long the page stays black before the grab ([capture] blank_ms).
        keep_snapshots: How many snapshots to keep ([capture] keep_snapshots).
        calibration: Current calibration, or None. The daemon replaces it after
            calibrating or fitting the board.
        lock: Held by every capture from blank to restore. The daemon must also hold
            it around calibrate(), so a capture can't un-pattern the page mid-read.
            Copies made with dataclasses.replace share it.
        page_changed_s: When the daemon last changed the page itself (monotonic s), or
            math.inf while it shows something other than the normal page, such as a
            flash or the night view (the daemon passes BoardController.page_changed_s).
            The change watcher settles after it, and the drift monitor waits while
            it's math.inf.
        motion_masks: Parts of the page that move by themselves (the idle view's news
            ticker), as (x, y, w, h) fractions of the board view; the change watcher's
            motion check leaves them out (BoardController.motion_masks).
    """

    camera: FrameSource
    set_mode: SetMode
    snapshot_dir: Path
    blank_ms: int
    keep_snapshots: int
    calibration: Calibration | None = None
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    page_changed_s: Callable[[], float] = lambda: -math.inf
    motion_masks: Callable[[], Sequence[FractionBox]] = lambda: ()


class CleanFrame(NamedTuple):
    """A clean capture before saving.

    Attributes:
        image: Board-view px when rectified, otherwise the raw camera frame.
        is_rectified: Whether `calibration` was applied.
        calibration: The rig's calibration at the time of the grab.
        raw: The camera frame before rectifying, in camera px (the drift check uses it).
    """

    image: np.ndarray
    is_rectified: bool
    calibration: Calibration | None
    raw: np.ndarray


async def keep_mode(mode: str) -> None:
    """A SetMode that leaves the page as it is: give a rig copy this for a projection-on look."""


async def _read_blank_frame(rig: CaptureRig) -> np.ndarray:
    """Blank the page, read a fresh frame, and always restore normal. Caller holds rig.lock."""
    # A stale camera would only time out after blanking the board for seconds.
    if rig.camera.latest() is None:
        raise CameraError(STALE_CAMERA_MESSAGE)
    try:
        await rig.set_mode(BLANK_MODE)
        # Time for the page to repaint and the projector to show it.
        await asyncio.sleep(rig.blank_ms / 1000)
        return await asyncio.to_thread(rig.camera.read_fresh)
    finally:
        await rig.set_mode(NORMAL_MODE)


async def grab_clean_frame(rig: CaptureRig) -> CleanFrame:
    """Blank the page, grab a fresh frame, restore the page, then rectify the frame.

    Raises:
        CameraError: If the camera is stale (the page is never blanked) or no
            fresh frame arrives (the page is restored first).
        Whatever set_mode raises (e.g. no board page connected).
    """
    async with rig.lock:
        frame = await _read_blank_frame(rig)
        calibration = rig.calibration
    image, is_rectified = await asyncio.to_thread(rectify_to_view, frame, calibration)
    if calibration is not None and not is_rectified:
        logger.warning(
            "frame size %s doesn't match calibration %s; recalibrate. Using the raw frame.",
            frame.shape[1::-1],
            calibration.camera_size,
        )
    return CleanFrame(image, is_rectified, calibration, frame)


async def clean_capture(rig: CaptureRig) -> tuple[Path, bool]:
    """Take a clean capture and save it as a snapshot PNG.

    Returns:
        (png_path, is_rectified). Unrectified means the PNG is the raw camera frame.

    Raises:
        CameraError: If the camera is stale or no fresh frame arrives.
        OSError: If the snapshot can't be written.
    """
    clean = await grab_clean_frame(rig)
    path = await asyncio.to_thread(save_snapshot, clean.image, rig.snapshot_dir, rig.keep_snapshots)
    return path, clean.is_rectified
