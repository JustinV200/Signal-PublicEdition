"""Tests for the Realigner on synthetic frames: a projector-only move carries the fit over (but
not if the camera moved too, even a little at a time), a bad solve or no movement changes
nothing, and after a re-align every item still lands on the same spot of the physical board."""

from pathlib import Path

import cv2
import numpy as np
import pytest

from whiteboard.camera import (
    Calibration,
    CalibrationError,
    CaptureRig,
    DriftReading,
    ReferencePhoto,
    board_quad_in_camera,
    board_quad_in_projector,
)
from whiteboard.config import AlignSettings
from whiteboard.daemon import camera_hooks
from whiteboard.daemon.board_view import BoardViewSync
from whiteboard.daemon.camera_hooks import HookContext
from whiteboard.daemon.realign import Realigner, realigner
from whiteboard.display.scene import SceneStore, item_from_dict, parse_quad, stage_homography
from whiteboard.display.server import BoardController

pytestmark = pytest.mark.asyncio

FIT_HEIGHT = 720
CAMERA_SIZE = (1920, 1080)
OLD_HOMOGRAPHY = np.diag([2 / 3, 2 / 3, 1.0])
BOARD_CORNERS = np.array([[300, 200], [1600, 180], [1620, 900], [280, 920]], dtype=np.float32)
# Someone bumped the projector: the board now sits this far over in projector px.
PROJECTOR_SHIFT = np.array([30.0, 12.0])
PROJECTOR_MOVE = np.array([[1, 0, PROJECTOR_SHIFT[0]], [0, 1, PROJECTOR_SHIFT[1]], [0, 0, 1]])
CAMERA_BUMP_PX = 40
# A bumped camera (the board shows up this far off in the frame) and a projector whose picture
# got squeezed sideways, so the board's measured aspect and logical width change.
CAMERA_SHIFT = np.array([25.0, 10.0])
SHIFT_BACK = np.array([[1, 0, -CAMERA_SHIFT[0]], [0, 1, -CAMERA_SHIFT[1]], [0, 0, 1]])
SQUEEZED_AND_BUMPED = np.diag([0.95, 1.0, 1.0]) @ OLD_HOMOGRAPHY @ SHIFT_BACK
MOVED_CORNERS = BOARD_CORNERS + CAMERA_SHIFT.astype(np.float32)
# Wall-like texture, so the camera-shift check has something to line up.
ROOM = cv2.GaussianBlur(
    np.random.default_rng(5).integers(0, 255, (CAMERA_SIZE[1], CAMERA_SIZE[0], 3), np.uint8),
    (9, 9),
    0,
)


class RoomCamera:
    """Blank-page frames of a textured room; `offset_px` moves the camera sideways."""

    def __init__(self) -> None:
        self.offset_px = 0

    def latest(self) -> np.ndarray:
        return np.roll(ROOM, self.offset_px, axis=1)

    def read_fresh(self) -> np.ndarray:
        return self.latest()


def marker(homography: np.ndarray, error_px: float = 0.5, created_at: str = "new") -> Calibration:
    return Calibration(homography, CAMERA_SIZE, (1280, 720), error_px, 6, created_at)


class Rig:
    """A fitted board with two items, its Realigner, and what the test watches."""

    def __init__(self, tmp_path: Path) -> None:
        self.camera = RoomCamera()
        self.board = BoardController(SceneStore(tmp_path / "scene.json"))
        rig = CaptureRig(self.camera, self.board.set_mode, tmp_path / "snapshots", 0, 1)
        old_marker = marker(OLD_HOMOGRAPHY, created_at="old")
        self.sync = BoardViewSync(self.board, rig, FIT_HEIGHT, old_marker)
        rig.set_mode = self.sync.set_mode
        reference = ReferencePhoto(tmp_path / "align-reference.png")
        # The last confirmed alignment's photo, taken before anything moved.
        reference.save(ROOM, old_marker)
        self.context = HookContext(
            self.board, rig, self.sync, tmp_path / "cal.json", FIT_HEIGHT, reference
        )
        self.realigner = Realigner(self.context, AlignSettings())
        self.toasts = 0

    async def fill(self) -> None:
        quad = board_quad_in_projector(BOARD_CORNERS, OLD_HOMOGRAPHY).tolist()
        await self.board.set_fit(parse_quad(quad))
        for item_id, x in (("left", 100), ("right", 1300)):
            box = {"id": item_id, "kind": "text", "x": x, "y": 300, "w": 150, "h": 60}
            await self.board.put_item(item_from_dict({**box, "content": "hi"}))
        self.sync.refresh()  # as any capture would, so the rig carries the fit

    def camera_point(self, x: float, y: float) -> np.ndarray:
        """Where a board-px point is projected, as the camera sees it (current alignment)."""
        stage = self.board.stage()
        size = (stage["width"], stage["height"])
        projector = stage_homography(self.board.scene.board_quad, size) @ [x, y, 1.0]
        camera = np.linalg.inv(self.sync.marker_calibration.homography) @ projector
        return camera[:2] / camera[2]


async def make_rig(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, solve: object, detected: np.ndarray | None
) -> Rig:
    """A rig whose marker solve returns (or raises) `solve` and whose board detection gives
    `detected`."""

    async def fake_calibrate(camera, show_pattern, clear_pattern, projector_size):
        if isinstance(solve, Exception):
            raise solve
        return solve

    rig = Rig(tmp_path)
    await rig.fill()

    async def count_toast(board: BoardController) -> None:
        rig.toasts += 1

    monkeypatch.setattr(camera_hooks, "calibrate", fake_calibrate)
    monkeypatch.setattr(realigner, "detect_board_quad", lambda frame, cal: detected)
    monkeypatch.setattr(realigner, "flash_toast", count_toast)
    return rig


@pytest.mark.parametrize("camera_moved", [False, True], ids=["camera-still", "camera-bumped"])
async def test_a_projector_move_carries_the_fit_over_only_if_the_camera_stayed_put(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, camera_moved: bool
) -> None:
    # The board outline can't be detected, as on the owner's board.
    new_marker = marker(PROJECTOR_MOVE @ OLD_HOMOGRAPHY)
    rig = await make_rig(tmp_path, monkeypatch, new_marker, detected=None)
    old_quad = np.array(rig.board.scene.board_quad)
    rig.camera.offset_px = CAMERA_BUMP_PX if camera_moved else 0

    result = await rig.realigner.realign()

    if camera_moved:  # can't tell what moved, so nothing changes
        assert not result.ok and not result.changed
        assert "camera moved" in result.message
        np.testing.assert_allclose(rig.board.scene.board_quad, old_quad)
        assert rig.toasts == 0
        return
    assert result.changed and rig.toasts == 1
    assert result.numbers["projector_drift_px"] > AlignSettings().drift_px
    # Old fit -> camera via the old H -> projector via the new H: shifted with the projector.
    np.testing.assert_allclose(rig.board.scene.board_quad, old_quad + PROJECTOR_SHIFT, atol=0.01)
    assert rig.sync.marker_calibration.created_at == "new"


@pytest.mark.parametrize(
    "solve",
    [CalibrationError("only 2 of 6 markers visible"), marker(OLD_HOMOGRAPHY, error_px=2.5)],
    ids=["markers-not-found", "reprojection-too-high"],
)
async def test_a_failed_or_inaccurate_solve_keeps_the_old_alignment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, solve: object
) -> None:
    rig = await make_rig(tmp_path, monkeypatch, solve, detected=None)
    old_marker, old_scene = rig.sync.marker_calibration, rig.board.scene

    result = await rig.realigner.realign()

    assert not result.ok and not result.changed
    assert rig.sync.marker_calibration is old_marker
    assert rig.board.scene == old_scene
    assert not rig.context.calibration_path.exists()


async def test_no_movement_changes_nothing_and_shows_no_toast(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    nudged = OLD_HOMOGRAPHY + np.diag([1e-4, 0.0, 0.0])  # a fresh solve is never exact
    rig = await make_rig(tmp_path, monkeypatch, marker(nudged), detected=None)
    old_marker, old_scene = rig.sync.marker_calibration, rig.board.scene

    result = await rig.realigner.realign()

    assert result.ok and not result.changed and rig.toasts == 0
    assert rig.sync.marker_calibration is old_marker
    assert rig.board.scene == old_scene
    assert not rig.context.calibration_path.exists()


async def test_after_board_drift_the_fit_moves_and_items_stay_on_the_board(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    rig = await make_rig(tmp_path, monkeypatch, marker(SQUEEZED_AND_BUMPED), MOVED_CORNERS)
    corners = [(item.x, item.y) for item in rig.board.scene.items]
    seen_before = [rig.camera_point(x, y) for x, y in corners]
    old_width = rig.board.stage()["width"]
    expected = board_quad_in_camera(np.array(rig.board.scene.board_quad), OLD_HOMOGRAPHY)
    # What the drift checks saw: the board 27 px off, in a frame of its own (a little noise).
    drift = DriftReading(26.9, MOVED_CORNERS + 0.5, expected, rig.context.rig.calibration)

    result = await rig.realigner.realign(drift)

    assert result.changed and rig.context.calibration_path.exists()
    assert rig.board.stage()["width"] != old_width  # so the items had to be rescaled
    corners = [(item.x, item.y) for item in rig.board.scene.items]
    seen_after = [rig.camera_point(x, y) for x, y in corners]
    # The camera moved too, so the same physical spot is CAMERA_SHIFT away in its frame.
    for before, after in zip(seen_before, seen_after, strict=True):
        np.testing.assert_allclose(after, before + CAMERA_SHIFT, atol=1.5)


async def test_a_camera_creeping_a_little_per_check_never_drags_the_fit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Regression: the projector and board never move, but the camera slides 7 px per check,
    # each step under the camera-shift limit. "Nothing moved" checks must not refresh the
    # reference photo, so the third check still measures 21 px from it and refuses.
    rig = await make_rig(tmp_path, monkeypatch, marker(OLD_HOMOGRAPHY), detected=None)
    old_quad = np.array(rig.board.scene.board_quad)
    for offset_px in (7, 14, 21):
        rig.camera.offset_px = offset_px
        shift_back = np.array([[1, 0, -offset_px], [0, 1, 0], [0, 0, 1]])
        solve = marker(OLD_HOMOGRAPHY @ shift_back, created_at=f"solve-{offset_px}")

        async def fake_calibrate(camera, show_pattern, clear_pattern, size, solve=solve):
            return solve

        monkeypatch.setattr(camera_hooks, "calibrate", fake_calibrate)
        result = await rig.realigner.realign()

    assert not result.ok and "camera moved" in result.message
    np.testing.assert_allclose(rig.board.scene.board_quad, old_quad)


async def test_a_kept_fit_from_the_calibration_array_still_saves(tmp_path: Path) -> None:
    # Regression: "fit kept" passed the calibration's numpy quad on to the scene, and the
    # save crashed on an ambiguous array truth value.
    rig = Rig(tmp_path)
    await rig.fill()
    old = np.array(rig.board.scene.board_quad, dtype=np.float32)
    quad = realigner._as_quad(None, old)
    assert all(isinstance(value, float) for point in quad for value in point)
    await rig.board.set_fit(quad)
    assert np.allclose(rig.board.scene.board_quad, old)
