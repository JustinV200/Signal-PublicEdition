"""The night view (sleep mode): the /api/night routes behind the daemon's token guard, as
tools/sleepmode calls them, the view hiding it goes back to, and nothing watching,
checking or flashing the board while it shows."""

import json
import math
import socket
import time
from pathlib import Path

import numpy as np
import pytest
from aiohttp.test_utils import TestClient, TestServer

from whiteboard.camera import BoardActivity, CaptureRig, ChangeWatcher, DriftMonitor
from whiteboard.camera.drift import IDLE_S
from whiteboard.config import AlignSettings, WatcherSettings
from whiteboard.daemon.request_guard import build_request_guard
from whiteboard.display.scene import NightViewError, SceneStore, item_from_dict
from whiteboard.display.server import BoardController, create_app

pytestmark = pytest.mark.asyncio

TOKEN = "s3cret"
AUTH = {"X-Signal-Token": TOKEN}
SEED = 20261019
TEXT_ITEM = {"id": "t1", "kind": "text", "x": 10, "y": 20, "w": 300, "h": 60, "content": "hi"}


async def test_night_routes_need_the_token_and_answer_sleepmode(tmp_path: Path) -> None:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    board = BoardController(SceneStore(tmp_path / "scene.json"))
    app = create_app(board)
    app.middlewares.insert(0, build_request_guard(TOKEN, port))
    client = TestClient(TestServer(app, host="127.0.0.1", port=port))
    await client.start_server()
    try:
        refused = [
            (await client.post(f"/api/night/{action}", json={})).status
            for action in ("show", "hide")
        ]
        foreign = await client.post(
            "/api/night/show", headers={**AUTH, "Origin": "https://evil.example"}
        )
        # Wake calls hide every time: outside the night view it's ok and changes nothing.
        idle_hide = await (await client.post("/api/night/hide", json={}, headers=AUTH)).json()
        saved_by_idle_hide = (tmp_path / "scene.json").exists()
        bad_seed = await client.post("/api/night/show", json={"seed": True}, headers=AUTH)
        # An older sleepmode still sends "sky"; it's ignored, never a 400.
        body = {"seed": SEED, "sky": False}
        shown = await (await client.post("/api/night/show", json=body, headers=AUTH)).json()
        status = await (await client.get("/api/status", headers=AUTH)).json()
        box = {"x": 0, "y": 0, "w": 50, "h": 50}
        flash = await client.post("/api/highlight", json=box, headers=AUTH)
        hidden = await (await client.post("/api/night/hide", json={}, headers=AUTH)).json()
    finally:
        await client.close()
    assert refused == [403, 403] and foreign.status == 403
    assert idle_hide == {"ok": True, "view": "items"} and not saved_by_idle_hide
    assert bad_seed.status == 400
    assert shown == {
        "ok": True,
        "view": "night",
        "seed": SEED,
        "previous_view": "items",
    }
    assert status["view"] == "night" and flash.status == 409
    assert hidden == {"ok": True, "view": "items"}


async def test_hiding_returns_to_the_view_it_hid_and_drawings_wait_under_it(
    tmp_path: Path,
) -> None:
    store = SceneStore(tmp_path / "scene.json")
    board = BoardController(store)
    await board.put_item(item_from_dict(TEXT_ITEM))
    await board.set_view("todo")
    await board.show_night(SEED)
    # A restarted daemon comes back to the night view, even from a scene.json saved when
    # it had a black option; showing it again still goes back to the view from before.
    saved = json.loads(store.path.read_text(encoding="utf-8"))
    store.path.write_text(json.dumps({**saved, "night": {**saved["night"], "sky": False}}))
    board = BoardController(store)
    await board.show_night(SEED)
    assert board.scene.view == "night" and board.scene.night.previous_view == "todo"
    await board.hide_night()
    assert board.scene.view == "todo" and [item.id for item in board.scene.items] == ["t1"]
    # A drawing made under the night view stays hidden, then shows when the night ends.
    await board.show_night(SEED)
    await board.put_item(item_from_dict({**TEXT_ITEM, "id": "t2"}))
    assert board.scene.view == "night"
    await board.hide_night()
    assert board.scene.view == "items" and [item.id for item in board.scene.items] == ["t1", "t2"]
    # Stored without `night` again, so older code can still load it after a rollback.
    assert "night" not in json.loads(store.path.read_text(encoding="utf-8"))


class LitBoard:
    """A camera on a lit, unchanging board (never too dark for the watcher)."""

    def latest(self) -> np.ndarray:
        return np.full((90, 160, 3), 200, dtype=np.uint8)

    def read_fresh(self) -> np.ndarray:
        return self.latest()


async def test_nothing_watches_checks_or_flashes_while_the_night_view_shows(
    tmp_path: Path,
) -> None:
    board = BoardController(SceneStore(tmp_path / "scene.json"))
    modes: list[str] = []
    realigns: list[object] = []

    async def set_mode(mode: str) -> None:
        modes.append(mode)
        await board.set_mode(mode)

    async def realign(drift: object) -> None:
        realigns.append(drift)

    async def on_board_changed(path: Path, bbox: tuple[int, int, int, int]) -> None:
        raise AssertionError("no change can be reported under the night view")

    rig = CaptureRig(LitBoard(), set_mode, tmp_path, 0, 1, page_changed_s=board.page_changed_s)
    watcher = ChangeWatcher(rig, WatcherSettings(), on_board_changed)
    monitor = DriftMonitor(rig, AlignSettings(), realign, BoardActivity(lambda: -math.inf))
    await board.show_night(SEED)
    assert board.page_changed_s() == math.inf
    # A whole night stepped on from the show, so the drift and marker checks fall due.
    night_s = 2 * AlignSettings().marker_check_s
    shown_s = time.monotonic()
    for now_s in np.arange(shown_s, shown_s + night_s, 60.0):
        await watcher.step(now_s)
        await monitor.step(now_s)
    assert modes == [] and realigns == []
    with pytest.raises(NightViewError):
        await board.set_mode("pattern")
    await board.hide_night()
    # Waking counts as a page change (on the real clock, at about shown_s, which the
    # steps' clock has run ahead of): the drift monitor waits IDLE_S before any flash.
    await monitor.step(time.monotonic() + IDLE_S - 1)
    assert modes == [] and realigns == []
    # Later both catch up: one watcher capture, a drift check and a marker check.
    await watcher.step(shown_s + night_s)
    await monitor.step(shown_s + night_s)
    assert modes == ["blank", "normal"] * 2 and realigns == [None]
