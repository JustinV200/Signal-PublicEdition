"""The change watcher: notices the owner drawing and reports the new ink once they stop.

Every `sample_s` it compares the live (projection-on) view with the last sample.
Motion marks the board "pending". Once nothing has moved for `stable_s`, it takes
one clean capture and diffs its ink against the last reported one. Only clean
(blank-page) captures are compared, so Claude's own projected drawings never count
as ink. Each clean capture blanks the board, so three rules keep those rare:
- settle: for `settle_s` after the daemon changed the page itself (any blank or
  marker flash, a drawing, the TODO view; CaptureRig.page_changed_s) or took its
  own capture, nothing is sampled, and the first sample after it is the new
  reference. The camera's exposure swing after a blank isn't someone drawing.
  While the night view shows, that time is math.inf, so nothing is sampled all night.
- throttle: captures are `min_interval_s` apart, unless the live view already
  shows LARGE_CHANGE_FACTOR x `ink_change_ratio` of new ink since the last one.
- moving parts: the rig's motion_masks (the idle view's scrolling news ticker) are
  blacked out of every live sample, so they never count as motion or as a large change.
  The drift monitor's "no motion for 30 s" rule reads last_motion_s, so it ignores them
  too. Clean captures blank the whole page, so ink drawn there still counts.
- dark: while the live camera frame's median grey is under `dark_floor`, the ink
  can't be read, so no capture is taken (darkness.DarkRoom, shared with the drift
  monitor through is_room_dark(); logged once per dark spell).
The daemon runs `run()` as a task when [watcher] enabled is true.
"""

import asyncio
import logging
import math
import time
from collections.abc import Awaitable, Callable, Sequence
from pathlib import Path

import numpy as np

from whiteboard.camera.calibration import Calibration, rectify_to_view
from whiteboard.camera.clean_capture import CaptureRig, CleanFrame, grab_clean_frame
from whiteboard.camera.darkness import DarkRoom
from whiteboard.camera.detection import added_ink_ratio, ink_change, motion_frame, motion_ratio
from whiteboard.camera.device import CameraError
from whiteboard.camera.snapshots import save_snapshot
from whiteboard.config import WatcherSettings
from whiteboard.shared import FractionBox

logger = logging.getLogger(__name__)

# New ink in the live view, as a multiple of ink_change_ratio, that skips min_interval_s.
LARGE_CHANGE_FACTOR = 10.0

BBox = tuple[int, int, int, int]
OnBoardChanged = Callable[[Path, BBox], Awaitable[None]]
# Given every clean capture and its monotonic time (the drift monitor checks it).
OnCleanFrame = Callable[[CleanFrame, float], Awaitable[None]]


def without_regions(image: np.ndarray, boxes: Sequence[FractionBox]) -> np.ndarray:
    """`image` with each (x, y, w, h) fraction box blacked out (a copy; as is if none).

    Black on both sides of a compare is no change, so whatever moves inside never counts.
    """
    if not boxes:
        return image
    masked = image.copy()
    height, width = image.shape[:2]
    for x, y, w, h in boxes:
        left, top = max(0, int(x * width)), max(0, int(y * height))
        right, bottom = math.ceil((x + w) * width), math.ceil((y + h) * height)
        masked[top:bottom, left:right] = 0
    return masked


class ChangeWatcher:
    """Watches the board through a CaptureRig and calls back when the ink changes.

    The first clean capture (taken on the first step) is the baseline and isn't
    reported. A new calibration or board fit resets the baseline.
    """

    def __init__(
        self,
        rig: CaptureRig,
        settings: WatcherSettings,
        on_board_changed: OnBoardChanged,
        on_clean_frame: OnCleanFrame | None = None,
    ) -> None:
        """Set up the watcher; call run() (or step()) to start watching.

        Args:
            rig: The daemon's shared capture rig (camera, page mode, calibration).
            settings: [watcher] timing and thresholds.
            on_board_changed: Async callback given the snapshot PNG path and the
                changed ink's (x, y, w, h) in that image's px. Should return quickly
                (queue the work), since the watcher waits for it.
            on_clean_frame: Optional async hook given each clean capture and its time,
                before the ink compare. Should return quickly and not raise.
        """
        self._rig = rig
        self._settings = settings
        self._on_board_changed = on_board_changed
        self._on_clean_frame = on_clean_frame
        self._previous_sample: np.ndarray | None = None
        # The live view just after the last capture settled, for the large-change check.
        self._live_reference: np.ndarray | None = None
        # Pending from the start, so the first step takes the baseline capture.
        self._is_pending = True
        self._dark_room = DarkRoom(rig.camera, settings.dark_floor)
        self._last_motion_s = -math.inf
        self._last_capture_s = -math.inf
        self._baseline: np.ndarray | None = None
        self._baseline_calibration: Calibration | None = None

    @property
    def last_motion_s(self) -> float:
        """Monotonic time of the last motion seen (-inf if none yet)."""
        return self._last_motion_s

    def is_room_dark(self) -> bool:
        """Whether the room is too dark to read the board now (the drift monitor asks too)."""
        return self._dark_room.is_dark()

    async def run(self) -> None:
        """Step every sample_s until the task is cancelled. A failed step is logged and skipped."""
        while True:
            try:
                await self.step(time.monotonic())
            except CameraError as error:
                logger.warning("change watcher: %s", error)
            except Exception:
                logger.exception("change watcher step failed; continuing")
            await asyncio.sleep(self._settings.sample_s)

    async def step(self, now_s: float) -> None:
        """Take one sample at monotonic time `now_s`, and a clean capture if one is due.

        Raises:
            CameraError, OSError, or whatever set_mode or the callback raise.
        """
        if self._is_settling(now_s):
            # The first sample after it is the new reference, for motion and for the
            # large-change check (Claude's drawings and the TODO view aren't new ink).
            self._previous_sample = self._live_reference = None
            return
        frame = self._rig.camera.latest()
        if frame is None:
            return
        view, is_rectified = rectify_to_view(frame, self._rig.calibration)
        # The masks are in board-view fractions; a raw camera frame doesn't line up.
        view = without_regions(view, self._rig.motion_masks() if is_rectified else ())
        sample = motion_frame(view)
        self._note_motion(sample, now_s)
        if self._live_reference is None:
            self._live_reference = view
        if await self._is_capture_due(now_s, view):
            await self._capture_and_compare(now_s)

    def _is_settling(self, now_s: float) -> bool:
        """Within settle_s of the daemon changing the page, or of this watcher's own capture."""
        changed_s = max(self._rig.page_changed_s(), self._last_capture_s)
        return now_s - changed_s < self._settings.settle_s

    def _note_motion(self, sample: np.ndarray, now_s: float) -> None:
        """Compare a sample with the previous one; motion makes a capture pending."""
        previous, self._previous_sample = self._previous_sample, sample
        if previous is None or previous.shape != sample.shape:
            return
        settings = self._settings
        if motion_ratio(previous, sample, settings.pixel_threshold) > settings.motion_ratio:
            self._is_pending = True
            self._last_motion_s = now_s

    async def _is_capture_due(self, now_s: float, view: np.ndarray) -> bool:
        """Pending, still for stable_s, light enough, and min_interval_s since the last
        capture or a large change in the live view."""
        settings = self._settings
        if not self._is_pending or now_s - self._last_motion_s < settings.stable_s:
            return False
        if self._dark_room.is_dark():
            return False
        if now_s - self._last_capture_s >= settings.min_interval_s:
            return True
        return await asyncio.to_thread(self._is_large_change, view)

    def _is_large_change(self, view: np.ndarray) -> bool:
        """Whether the live view shows LARGE_CHANGE_FACTOR x ink_change_ratio of new ink."""
        reference = self._live_reference
        if reference is None or reference.shape != view.shape:
            return False
        ratio = added_ink_ratio(reference, view)
        return ratio >= LARGE_CHANGE_FACTOR * self._settings.ink_change_ratio

    async def _capture_and_compare(self, now_s: float) -> None:
        """Clean-capture, diff the ink against the baseline, and report a real change.

        TODO: someone standing still in front of the board for stable_s is in the
        clean capture. Their body is mostly too wide to be ink (detection's
        BOARD_FILL_PX), but its uneven edge and any arm narrower than that still read
        as new ink, and an arm reads as a large change in the live view too, so its
        capture skips min_interval_s. An occlusion check (a large dark blob in the changed
        area) would skip those captures.
        """
        self._last_capture_s = now_s
        # If the grab fails (camera gone, page not connected), wait for new motion
        # rather than blanking the board again every min_interval_s. Only a missing
        # baseline keeps retrying, so the first capture isn't skipped for good.
        self._is_pending = self._baseline is None
        clean = await grab_clean_frame(self._rig)
        image, calibration = clean.image, clean.calibration
        self._is_pending = False
        # Re-baselined once this capture's settle_s is over.
        self._previous_sample = self._live_reference = None
        if self._on_clean_frame is not None:
            await self._on_clean_frame(clean, now_s)
        if (
            self._baseline is None
            or calibration is not self._baseline_calibration
            or image.shape != self._baseline.shape
        ):
            self._set_baseline(image, calibration)
            return
        change = await asyncio.to_thread(ink_change, self._baseline, image)
        # Below the threshold the baseline stays, so small additions add up
        # until they're worth reporting.
        if change.bbox is None or change.ratio < self._settings.ink_change_ratio:
            return
        self._set_baseline(image, calibration)
        rig = self._rig
        path = await asyncio.to_thread(save_snapshot, image, rig.snapshot_dir, rig.keep_snapshots)
        logger.info("board changed: %.4f of pixels, bbox %s", change.ratio, change.bbox)
        await self._on_board_changed(path, change.bbox)

    def _set_baseline(self, image: np.ndarray, calibration: Calibration | None) -> None:
        """Make `image` the capture later ones are compared against."""
        self._baseline = image
        self._baseline_calibration = calibration
