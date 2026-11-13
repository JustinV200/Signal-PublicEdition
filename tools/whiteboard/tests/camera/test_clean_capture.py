"""Tests for clean_capture: the page always goes back to normal, a stale camera never
blanks it, and overlapping captures take turns."""

import asyncio
from pathlib import Path

import numpy as np
import pytest

from whiteboard.camera import BLANK_MODE, NORMAL_MODE, CameraError, CaptureRig, clean_capture

GREY_FRAME = np.full((720, 1280, 3), 128, np.uint8)


class FakeCamera:
    """A camera whose fresh read either returns a grey frame or raises."""

    def __init__(self, error: Exception | None = None, is_stale: bool = False) -> None:
        self._error = error
        self._is_stale = is_stale

    def latest(self) -> np.ndarray | None:
        return None if self._is_stale else GREY_FRAME

    def read_fresh(self) -> np.ndarray:
        if self._error is not None:
            raise self._error
        return GREY_FRAME


def make_rig(camera: FakeCamera, modes: list[str], tmp_path: Path) -> CaptureRig:
    async def set_mode(mode: str) -> None:
        modes.append(mode)
        await asyncio.sleep(0)  # let another capture run here if nothing stops it

    return CaptureRig(camera, set_mode, tmp_path, blank_ms=0, keep_snapshots=2)


@pytest.mark.asyncio
async def test_mode_is_restored_when_the_grab_fails(tmp_path: Path) -> None:
    modes: list[str] = []
    rig = make_rig(FakeCamera(CameraError("unplugged")), modes, tmp_path)

    with pytest.raises(CameraError):
        await clean_capture(rig)

    assert modes == [BLANK_MODE, NORMAL_MODE]


@pytest.mark.asyncio
async def test_stale_camera_fails_without_blanking(tmp_path: Path) -> None:
    modes: list[str] = []
    rig = make_rig(FakeCamera(is_stale=True), modes, tmp_path)

    with pytest.raises(CameraError, match="no frames"):
        await clean_capture(rig)

    assert modes == []


@pytest.mark.asyncio
async def test_overlapping_captures_take_turns(tmp_path: Path) -> None:
    modes: list[str] = []
    rig = make_rig(FakeCamera(), modes, tmp_path)

    await asyncio.gather(clean_capture(rig), clean_capture(rig))

    assert modes == [BLANK_MODE, NORMAL_MODE] * 2


@pytest.mark.asyncio
async def test_uncalibrated_capture_saves_raw_frame_and_prunes(tmp_path: Path) -> None:
    modes: list[str] = []
    rig = make_rig(FakeCamera(), modes, tmp_path)

    paths = [await clean_capture(rig) for _ in range(3)]

    assert all(is_rectified is False for _path, is_rectified in paths)
    assert sorted(tmp_path.glob("*.png")) == [path for path, _ in paths[1:]]
    assert modes == [BLANK_MODE, NORMAL_MODE] * 3
