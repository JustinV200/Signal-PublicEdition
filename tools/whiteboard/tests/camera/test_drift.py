"""Tests for DriftMonitor on synthetic camera frames: noise never triggers, a board that
stays shifted for two checks does, a one-off shift doesn't, and nothing (photo checks,
re-aligns, marker checks) runs unless idle, and no timed check while the room is dark."""

from dataclasses import dataclass, field, replace
from pathlib import Path

import cv2
import numpy as np
import pytest

from whiteboard.camera import (
    BLANK_MODE,
    BoardActivity,
    Calibration,
    CaptureRig,
    DriftMonitor,
    DriftReading,
    board_quad_in_projector,
    check_drift_now,
    grab_clean_frame,
)
from whiteboard.config import AlignSettings

pytestmark = pytest.mark.asyncio

CAMERA_SIZE = (1920, 1080)
# Camera px to projector px: the projection fills the camera frame.
HOMOGRAPHY = np.diag([2 / 3, 2 / 3, 1.0])
BOARD_CORNERS = np.array([[300, 200], [1600, 180], [1620, 900], [280, 920]], dtype=np.float32)
SHIFT_PX = 30.0
CHECK_S = AlignSettings().check_s
# Marker checks are tested on their own; elsewhere they never come due.
NO_MARKER_CHECKS = AlignSettings(marker_check_s=1e12)
LONG_AGO_S = -1e9


class FakeCamera:
    """A blank-page camera view: a bright board on a darker wall, with sensor noise."""

    def __init__(self) -> None:
        self.corners = BOARD_CORNERS.copy()
        self.modes: list[str] = []
        self._rng = np.random.default_rng(3)

    def latest(self) -> np.ndarray:
        width, height = CAMERA_SIZE
        frame = np.full((height, width), 70, dtype=np.uint8)
        cv2.fillConvexPoly(frame, self.corners.astype(np.int32), 200)
        noisy = frame + self._rng.normal(0, 3, frame.shape)
        return cv2.cvtColor(np.clip(noisy, 0, 255).astype(np.uint8), cv2.COLOR_GRAY2BGR)

    def read_fresh(self) -> np.ndarray:
        return self.latest()

    async def set_mode(self, mode: str) -> None:
        self.modes.append(mode)


@dataclass
class Harness:
    """A monitor over a fitted fake board, with the state a test drives and checks."""

    camera: FakeCamera
    rig: CaptureRig
    monitor: DriftMonitor | None = None
    last_motion_s: float = LONG_AGO_S
    is_busy: bool = False
    is_dark: bool = False
    realigns: list[DriftReading | None] = field(default_factory=list)

    async def watcher_capture(self, now_s: float) -> None:
        """What the change watcher does: a clean capture handed to the monitor."""
        assert self.monitor is not None
        await self.monitor.on_clean_frame(await grab_clean_frame(self.rig), now_s)


def make_harness(tmp_path: Path, settings: AlignSettings = NO_MARKER_CHECKS) -> Harness:
    camera = FakeCamera()
    fit = board_quad_in_projector(BOARD_CORNERS, HOMOGRAPHY)
    calibration = Calibration(HOMOGRAPHY, CAMERA_SIZE, (1280, 720), 0.5, 6, "", fit, (1300, 720))
    harness = Harness(camera, CaptureRig(camera, camera.set_mode, tmp_path, 0, 1, calibration))

    async def realign(drift: DriftReading | None) -> None:
        harness.realigns.append(drift)

    activity = BoardActivity(
        lambda: harness.last_motion_s, lambda: harness.is_busy, lambda: harness.is_dark
    )
    harness.monitor = DriftMonitor(harness.rig, settings, realign, activity)
    return harness


async def test_noise_alone_never_counts_as_drift(tmp_path: Path) -> None:
    harness = make_harness(tmp_path)
    reading = await check_drift_now(harness.rig)
    assert reading.error_px is not None and reading.error_px < 2  # the board is found
    for check in range(4):
        await harness.monitor.step(check * CHECK_S)
    assert harness.realigns == [] and not harness.monitor.is_drifted


async def test_a_board_shifted_on_two_checks_in_a_row_triggers_a_realign(tmp_path: Path) -> None:
    harness = make_harness(tmp_path)
    harness.camera.corners = BOARD_CORNERS + SHIFT_PX
    # The first drifted check comes from a watcher capture, the second from the timer.
    await harness.watcher_capture(0)
    assert harness.realigns == [] and harness.monitor.is_drifted
    await harness.monitor.step(CHECK_S)
    assert len(harness.realigns) == 1
    assert harness.realigns[0].error_px == pytest.approx(SHIFT_PX * np.sqrt(2), abs=2)


async def test_a_check_that_cant_see_the_outline_keeps_the_board_drifted(tmp_path: Path) -> None:
    harness = make_harness(tmp_path)
    harness.camera.corners = BOARD_CORNERS + SHIFT_PX
    await harness.watcher_capture(0)
    # Someone in front of the board hides its outline: that says nothing either way.
    harness.camera.corners = np.zeros_like(BOARD_CORNERS)
    await harness.watcher_capture(1)
    assert harness.monitor.is_drifted
    # A re-align (a new calibration object) starts over.
    harness.rig.calibration = replace(harness.rig.calibration)
    await harness.watcher_capture(2)
    assert not harness.monitor.is_drifted


async def test_a_single_shift_does_not_trigger(tmp_path: Path) -> None:
    harness = make_harness(tmp_path)
    harness.camera.corners = BOARD_CORNERS + SHIFT_PX  # e.g. someone leaning on the board
    await harness.monitor.step(0)
    harness.camera.corners = BOARD_CORNERS
    await harness.monitor.step(CHECK_S)
    harness.camera.corners = BOARD_CORNERS + SHIFT_PX
    await harness.monitor.step(2 * CHECK_S)
    assert harness.realigns == []


async def test_checks_and_realigns_wait_until_the_board_is_idle(tmp_path: Path) -> None:
    harness = make_harness(tmp_path)
    harness.camera.corners = BOARD_CORNERS + SHIFT_PX
    harness.last_motion_s = 0
    await harness.monitor.step(10)  # someone moved 10 s ago
    assert harness.camera.modes == []  # no timed check: the page was never blanked

    # Two watcher captures confirm the drift, but an agent turn is running.
    await harness.watcher_capture(40)
    await harness.watcher_capture(50)
    harness.is_busy = True
    await harness.monitor.step(60)
    assert harness.realigns == []

    harness.is_busy = False
    await harness.monitor.step(65)
    assert len(harness.realigns) == 1


@pytest.mark.parametrize("blocker", ["is_busy", "is_dark"])
async def test_timed_checks_wait_while_busy_or_dark_then_resume(
    tmp_path: Path, blocker: str
) -> None:
    harness = make_harness(tmp_path, AlignSettings(marker_check_s=60))
    setattr(harness, blocker, True)  # an agent turn runs, or the room is dark
    await harness.monitor.step(0)  # starts the marker clock: no flash right at startup
    await harness.monitor.step(60)  # the photo and marker checks are both due
    assert harness.camera.modes == [] and harness.realigns == []

    setattr(harness, blocker, False)
    await harness.monitor.step(65)
    await harness.monitor.step(70)  # the next marker check is 60 s later
    assert BLANK_MODE in harness.camera.modes and harness.realigns == [None]
