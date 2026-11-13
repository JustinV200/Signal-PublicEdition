"""resume_night: a daemon started while sleep mode is on opens on that night's sky."""

import json
from pathlib import Path

import pytest

from whiteboard.daemon.night_resume import resume_night
from whiteboard.display.scene import SceneStore
from whiteboard.display.server import BoardController

pytestmark = pytest.mark.asyncio


@pytest.mark.parametrize(
    ("state", "expected"),
    [
        # 01:12 belongs to the evening before: same seed sleep mode used.
        ({"is_asleep": True, "since": "2026-10-25T01:12:00", "night_sky": True}, (20261024, True)),
        ({"is_asleep": False, "since": "2026-10-25T01:12:00"}, None),
        ("not json", None),
        (None, None),
    ],
)
async def test_resume_night_follows_sleep_modes_state(tmp_path, state, expected) -> None:
    state_file = tmp_path / "state.json"
    if state is not None:
        state_file.write_text(state if isinstance(state, str) else json.dumps(state))
    board = BoardController(SceneStore(tmp_path / "scene.json"))
    await resume_night(board, state_file)
    night = board.scene.night
    assert ((night.seed, night.sky) if night else None) == expected


async def test_resume_night_retries_a_read_mid_replace(tmp_path, monkeypatch) -> None:
    # sleepmode writes with os.replace; on Windows a read landing mid-replace gets PermissionError.
    state_file = tmp_path / "state.json"
    state_file.write_text(json.dumps({"is_asleep": True, "since": "2026-10-25T01:12:00"}))
    real_read = Path.read_bytes
    failures = iter([PermissionError("delete pending")])

    def flaky_read(self: Path) -> bytes:
        error = next(failures, None) if self == state_file else None
        if error:
            raise error
        return real_read(self)

    monkeypatch.setattr(Path, "read_bytes", flaky_read)
    board = BoardController(SceneStore(tmp_path / "scene.json"))
    await resume_night(board, state_file)
    assert board.scene.night is not None
