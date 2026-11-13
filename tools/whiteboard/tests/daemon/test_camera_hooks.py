"""Camera hooks: calibrate-then-fit holds the capture lock throughout and still finishes
(no self-deadlock), and a raw look still reports the projected items."""

import asyncio

import numpy as np
import pytest

from whiteboard.camera import Calibration, CaptureRig, ReferencePhoto
from whiteboard.daemon import camera_hooks
from whiteboard.daemon.board_view import BoardViewSync
from whiteboard.daemon.camera_hooks import CameraHooks, HookContext
from whiteboard.display.scene import SceneStore, item_from_dict
from whiteboard.display.server import BoardController

pytestmark = pytest.mark.asyncio

FIT_HEIGHT = 720
BOARD_CORNERS = np.array([[140, 60], [1140, 60], [1140, 560], [140, 560]], dtype=np.float32)
DEADLOCK_TIMEOUT_S = 5.0


class BlackCamera:
    """A frame source that always has a fresh black 1080p frame."""

    def latest(self) -> np.ndarray:
        return np.zeros((1080, 1920, 3), dtype=np.uint8)

    def read_fresh(self) -> np.ndarray:
        return self.latest()


def make_hooks(tmp_path) -> tuple[BoardController, CaptureRig, CameraHooks]:
    """Hooks over a black camera and an empty, uncalibrated board."""
    board = BoardController(SceneStore(tmp_path / "scene.json"))
    rig = CaptureRig(BlackCamera(), board.set_mode, tmp_path / "snapshots", 0, 1)
    sync = BoardViewSync(board, rig, FIT_HEIGHT, None)
    rig.set_mode = sync.set_mode
    reference = ReferencePhoto(tmp_path / "align-reference.png")
    context = HookContext(board, rig, sync, tmp_path / "calibration.json", FIT_HEIGHT, reference)
    hooks = CameraHooks(context)
    return board, rig, hooks


async def test_calibrate_then_fit_runs_under_the_lock_and_sets_the_fit(
    tmp_path, monkeypatch
) -> None:
    board, rig, hooks = make_hooks(tmp_path)
    lock_held_during = []

    async def fake_calibrate(camera, show_pattern, clear_pattern, projector_size):
        lock_held_during.append(rig.lock.locked())
        return Calibration(np.eye(3), (1920, 1080), (1280, 720), 0.4, 6, "2026-10-19T00:00Z")

    def fake_detect(frame, calibration):
        lock_held_during.append(rig.lock.locked())
        return BOARD_CORNERS

    monkeypatch.setattr(camera_hooks, "calibrate", fake_calibrate)
    monkeypatch.setattr(camera_hooks, "detect_board_quad", fake_detect)

    result = await asyncio.wait_for(hooks.calibrate(), DEADLOCK_TIMEOUT_S)

    assert lock_held_during == [True, True]
    assert not rig.lock.locked()
    assert result["ok"] and result["board_found"]
    assert board.scene.board_quad is not None
    assert rig.calibration.board_quad is not None
    assert (tmp_path / "calibration.json").is_file()
    # A deliberate recalibration also gives the re-align a fresh reference photo.
    assert ReferencePhoto(tmp_path / "align-reference.png").load(rig.calibration) is not None


async def test_a_raw_look_lists_the_projected_items(tmp_path) -> None:
    board, _, hooks = make_hooks(tmp_path)
    item = {"kind": "text", "content": "hi", "x": 0, "y": 0, "w": 9, "h": 9}
    await board.put_item(item_from_dict(item))

    result = await hooks.look_raw(clean=False)

    assert [item["content"] for item in result["items"]] == ["hi"]
