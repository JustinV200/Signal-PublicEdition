"""The drift monitor: notices when the board no longer sits where the alignment says it does.

If the camera, the projector or the board moves, the fit made at calibration
time goes stale. Each check finds the board's outline in a blank-page camera
frame (detect_board_quad) and compares it with the fit mapped back into camera
px. Two checks in a row off by more than [align] drift_px ask the daemon to
re-align. A check that finds no outline counts for nothing either way, because
someone standing in front of the board can hide its edges. Checks come from the
change watcher's own captures (no extra blank) and, while the board is idle,
from a capture of our own every [align] check_s seconds. A blank photo can't
show the projector moving, so every [align] marker_check_s while idle the
monitor also asks for a marker check (realign with no reading), which flashes
the markers and solves afresh. Neither timed check runs while the room is too dark
(BoardActivity.is_dark): a blank photo shows nothing then, and a marker flash in a
dark room is the most visible flash of all. Nothing runs until the page has been
the normal board, unchanged, for IDLE_S (CaptureRig.page_changed_s): never during a
fit outline, another flash, or sleep mode's night view (math.inf all night), and
checks that came due overnight wait IDLE_S after waking instead of flashing at once.
Only OpenCV, no Claude.
"""

import asyncio
import logging
import math
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

import numpy as np

from whiteboard.camera.calibration import Calibration, board_quad_in_camera, detect_board_quad
from whiteboard.camera.clean_capture import CaptureRig, CleanFrame, grab_clean_frame
from whiteboard.camera.device import CameraError
from whiteboard.config import AlignSettings

logger = logging.getLogger(__name__)

# Drifted checks in a row before re-aligning: one can be a person or a shadow.
DRIFT_STRIKES = 2
# The board counts as idle after this long without motion or a page change.
IDLE_S = 30.0
# How often run() looks at the clock; the checks themselves are check_s apart.
TICK_S = 5.0


@dataclass(frozen=True)
class DriftReading:
    """One drift check.

    Attributes:
        error_px: Mean corner distance between detected and expected, in camera px,
            or None when there was nothing to compare (see `note`).
        detected: The board outline found in the frame (camera px, TL, TR, BR, BL), or None.
        expected: Where the current fit says the board is (camera px), or None.
        calibration: The calibration (with its fit) the check was made against.
        note: Why there's no error, or "".
    """

    error_px: float | None
    detected: np.ndarray | None
    expected: np.ndarray | None
    calibration: Calibration | None
    note: str = ""


@dataclass(frozen=True)
class BoardActivity:
    """What the monitor asks before disturbing the board.

    Attributes:
        last_motion_s: Monotonic time of the last motion (the change watcher's).
        is_busy: Whether a board agent turn is running or queued.
        is_dark: Whether the room is too dark to read the board (the change
            watcher's is_room_dark); asked only when a timed check is due.
    """

    last_motion_s: Callable[[], float]
    is_busy: Callable[[], bool] = lambda: False
    is_dark: Callable[[], bool] = lambda: False


Realign = Callable[[DriftReading | None], Awaitable[object]]
"""Re-aligns after board drift (given the last drifted reading), or runs a marker check (None)."""


def corner_error(quad_a: np.ndarray, quad_b: np.ndarray) -> float:
    """Mean distance between matching corners of two (4, 2) quads, in their px."""
    return float(np.linalg.norm(quad_a - quad_b, axis=1).mean())


def measure_drift(frame: np.ndarray, calibration: Calibration | None) -> DriftReading:
    """Compare the board outline in a raw blank-page frame with the current fit.

    Args:
        frame: Camera frame (camera px), taken with the page blank.
        calibration: The rig's calibration including its board fit.

    Returns:
        The reading; error_px is None when uncalibrated, unfitted, the frame size
        doesn't match, or no outline was found.
    """
    if calibration is None or calibration.board_quad is None:
        return DriftReading(None, None, None, calibration, "no board fit to check")
    if tuple(frame.shape[1::-1]) != tuple(calibration.camera_size):
        return DriftReading(None, None, None, calibration, "frame size doesn't match calibration")
    expected = board_quad_in_camera(calibration.board_quad, calibration.homography)
    detected = detect_board_quad(frame, calibration)
    if detected is None:
        note = "board outline not found (edges hidden?)"
        return DriftReading(None, None, expected, calibration, note)
    return DriftReading(corner_error(detected, expected), detected, expected, calibration)


async def check_drift_now(rig: CaptureRig) -> DriftReading:
    """Take one clean capture and measure drift on it (used by checks and `whiteboard align`).

    Raises:
        CameraError: The camera is stale or no fresh frame arrived.
    """
    clean = await grab_clean_frame(rig)
    return await asyncio.to_thread(measure_drift, clean.raw, clean.calibration)


class DriftMonitor:
    """Counts drifted checks and calls `realign` after DRIFT_STRIKES in a row, when idle.

    Also calls `realign(None)` every marker_check_s while idle, counted from the first step.
    """

    def __init__(
        self,
        rig: CaptureRig,
        settings: AlignSettings,
        realign: Realign,
        activity: BoardActivity,
    ) -> None:
        """Set up the monitor; run() (or step()) does the work.

        Args:
            rig: The daemon's shared capture rig.
            settings: [align] check_s, marker_check_s and drift_px.
            realign: Called with the last drifted reading, or None for a marker check.
                Must hold rig.lock itself.
            activity: Motion and agent state, for the idle rule.
        """
        self._rig = rig
        self._settings = settings
        self._realign = realign
        self._activity = activity
        self._last_check_s = -math.inf
        self._last_marker_check_s: float | None = None
        self._strikes = 0
        self._last_drift: DriftReading | None = None
        self._strike_calibration: Calibration | None = None
        # The latest check that found the board's outline (see is_drifted).
        self._last_outline: DriftReading | None = None

    @property
    def is_drifted(self) -> bool:
        """Whether the latest check that found the board's outline was over drift_px.

        The change watcher's on_clean_frame runs before its on_board_changed, so while
        a change is reported this is usually the reading of that change's own capture.
        A check that found no outline (someone in front of a corner) says nothing, so
        the one before it still counts; a new calibration or fit clears it.
        """
        reading = self._last_outline
        return reading is not None and reading.error_px > self._settings.drift_px

    async def run(self) -> None:
        """Step every TICK_S until cancelled. A failed step is logged and skipped."""
        while True:
            try:
                await self.step(time.monotonic())
            except CameraError as error:
                logger.warning("drift check: %s", error)
            except Exception:
                logger.exception("drift check failed; continuing")
            await asyncio.sleep(TICK_S)

    async def step(self, now_s: float) -> None:
        """When idle: a timed check if one is due, then a re-align if drift was confirmed,
        else a marker check if one is due.

        Raises:
            CameraError, or whatever the capture or `realign` raise.
        """
        if self._last_marker_check_s is None:
            # No marker flash right at startup, while the page may still be loading.
            self._last_marker_check_s = now_s
        if not self._is_idle(now_s):
            return
        if self._is_timed_check_due(self._last_check_s, self._settings.check_s, now_s):
            self._last_check_s = now_s
            self._record(await check_drift_now(self._rig))
        if self._strikes >= DRIFT_STRIKES and self._last_drift is not None:
            # Reset first: a failed re-align then waits for two fresh drifted
            # checks instead of flashing the marker pattern every tick.
            drift, self._strikes = self._last_drift, 0
            # A re-align solves the markers too, so it counts as a marker check.
            self._last_marker_check_s = now_s
            await self._realign(drift)
        elif self._is_timed_check_due(
            self._last_marker_check_s, self._settings.marker_check_s, now_s
        ):
            self._last_marker_check_s = now_s
            await self._realign(None)

    async def on_clean_frame(self, clean: CleanFrame, now_s: float) -> None:
        """Change-watcher hook: check a capture it already took. Never raises."""
        try:
            reading = await asyncio.to_thread(measure_drift, clean.raw, clean.calibration)
        except Exception:
            logger.exception("drift check on a watcher capture failed")
            return
        self._last_check_s = now_s
        self._record(reading)

    def _is_timed_check_due(self, last_s: float, interval_s: float, now_s: float) -> bool:
        """`interval_s` since `last_s`, and the room light enough to see anything.

        A check skipped in the dark stays due, so it runs as soon as the light is back.
        """
        return now_s - last_s >= interval_s and not self._activity.is_dark()

    def _is_idle(self, now_s: float) -> bool:
        """No motion and no page change for IDLE_S, and no agent turn running or queued.

        page_changed_s is math.inf while a flash or the night view shows, so that's
        never idle; once the night view ends, its hide counts as the page change.
        """
        if now_s - self._rig.page_changed_s() < IDLE_S:
            return False
        activity = self._activity
        return now_s - activity.last_motion_s() >= IDLE_S and not activity.is_busy()

    def _record(self, reading: DriftReading) -> None:
        """Count a drifted reading, reset on a good one, ignore one with nothing to compare."""
        # Strikes only add up against one alignment; a new calibration or fit starts over.
        if reading.calibration is not self._strike_calibration:
            self._strikes, self._strike_calibration = 0, reading.calibration
            self._last_outline = None
        if reading.error_px is None:
            logger.debug("drift check skipped: %s", reading.note)
            return
        self._last_outline = reading
        if reading.error_px <= self._settings.drift_px:
            self._strikes = 0
            return
        self._strikes += 1
        self._last_drift = reading
        logger.info(
            "board drift %.1f px (limit %.1f), check %d of %d",
            reading.error_px,
            self._settings.drift_px,
            self._strikes,
            DRIFT_STRIKES,
        )
