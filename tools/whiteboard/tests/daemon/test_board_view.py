"""The fit wiring: a board quad set on the scene (as POST /api/fit does) reaches the capture rig."""

import numpy as np
import pytest

from whiteboard.camera import Calibration, CaptureRig
from whiteboard.daemon.board_view import BoardViewSync
from whiteboard.display.scene import SceneStore, parse_quad
from whiteboard.display.server import BoardController

pytestmark = pytest.mark.asyncio

FIT_HEIGHT = 720
# A board twice as wide as it is tall, inside the 1280x720 projector area.
BOARD_QUAD = [[140, 60], [1140, 60], [1140, 560], [140, 560]]


async def test_scene_fit_changes_reach_the_rig_on_the_next_capture(tmp_path) -> None:
    board = BoardController(SceneStore(tmp_path / "scene.json"))
    rig = CaptureRig(
        camera=None, set_mode=board.set_mode, snapshot_dir=tmp_path, blank_ms=0, keep_snapshots=1
    )
    marker = Calibration(np.eye(3), (1920, 1080), (1280, 720), 0.5, 6, "2026-10-19T00:00:00+00:00")
    sync = BoardViewSync(board, rig, FIT_HEIGHT, marker)
    assert rig.calibration.board_quad is None

    await board.set_fit(parse_quad(BOARD_QUAD))
    await sync.set_mode("blank")  # every capture switches mode first
    fitted = rig.calibration
    await sync.set_mode("normal")
    assert rig.calibration is fitted  # unchanged fit: same object, watcher baseline kept

    await board.set_fit(None)
    await sync.set_mode("blank")
    assert np.allclose(fitted.board_quad, BOARD_QUAD)
    assert fitted.board_size == (1440, FIT_HEIGHT)
    assert rig.calibration.board_quad is None and rig.calibration.board_size is None
