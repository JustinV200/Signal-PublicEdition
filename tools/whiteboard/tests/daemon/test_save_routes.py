"""The /api/saves routes on the daemon's guarded app: token required, then save and load work."""

import socket

import pytest
from aiohttp.test_utils import TestClient, TestServer

from whiteboard.daemon.loading_box import LoadingBox
from whiteboard.daemon.request_guard import build_request_guard
from whiteboard.daemon.save_routes import SaveContext, add_save_routes
from whiteboard.display.scene import SceneStore
from whiteboard.display.server import BoardController, create_app
from whiteboard.saves import SaveStore

pytestmark = pytest.mark.asyncio

TOKEN = "s3cret"
AUTH = {"X-Signal-Token": TOKEN}
TEXT_ITEM = {"id": "t1", "kind": "text", "x": 10, "y": 20, "w": 300, "h": 60, "content": "hi"}


async def test_saves_need_the_token_then_save_and_load_without_a_camera(tmp_path) -> None:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    board = BoardController(SceneStore(tmp_path / "scene.json"))
    app = create_app(board)
    app.middlewares.insert(0, build_request_guard(TOKEN, port))
    # Saves must sit under <repo>/tools/whiteboard/.state/, so fake the repo in tmp_path.
    store = SaveStore(tmp_path / "tools/whiteboard/.state/boards", repo_root=tmp_path)
    add_save_routes(app, SaveContext(board, store, rig=None))
    client = TestClient(TestServer(app, host="127.0.0.1", port=port))
    await client.start_server()
    try:
        refused = await client.post("/api/saves", json={"name": "plan"})
        await client.post("/api/items", json=TEXT_ITEM, headers=AUTH)
        await LoadingBox(board).show(None)
        saved = await (await client.post("/api/saves", json={"name": "plan"}, headers=AUTH)).json()
        again = await client.post("/api/saves", json={"name": "Plan"}, headers=AUTH)
        await client.post("/api/clear", headers=AUTH)
        load_body = {"name": "plan", "mode": "overlay"}
        loaded = await (await client.post("/api/saves/load", json=load_body, headers=AUTH)).json()
    finally:
        await client.close()
    assert refused.status == 403
    assert saved["slug"] == "plan" and saved["has_ink"] is False and "camera" in saved["note"]
    assert again.status == 400
    assert loaded["item_count"] == 1 and loaded["mode"] == "overlay"
    # The thinking box was up when saving; the save must not have kept it.
    assert [item.id for item in board.scene.items] == ["t1"]
