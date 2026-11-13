"""The /api/todo routes on the daemon's guarded app: token required, then errors map to statuses."""

import socket
from datetime import datetime
from pathlib import Path

import pytest
from aiohttp.test_utils import TestClient, TestServer

from whiteboard.daemon.request_guard import build_request_guard
from whiteboard.daemon.todo import TodoController, TodoFiles, add_todo_routes
from whiteboard.display.scene import SceneStore
from whiteboard.display.server import BoardController, create_app

pytestmark = pytest.mark.asyncio

TOKEN = "s3cret"
AUTH = {"X-Signal-Token": TOKEN}


async def test_todo_routes_need_the_token_then_work(tmp_path: Path, life_dir: Path) -> None:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    board = BoardController(SceneStore(tmp_path / "scene.json"))
    files = TodoFiles(life_dir, tmp_path / "todo.json", tmp_path / "todo.log")
    app = create_app(board)
    app.middlewares.insert(0, build_request_guard(TOKEN, port))
    add_todo_routes(app, TodoController(board, files, lambda: datetime(2026, 10, 19, 12)))
    client = TestClient(TestServer(app, host="127.0.0.1", port=port))
    await client.start_server()
    try:
        refused = [
            (await client.post(f"/api/todo/{action}", json={"item": "A19"})).status
            for action in ("sync", "show", "hide", "done", "undone")
        ]
        foreign = await client.post(
            "/api/todo/show", headers={**AUTH, "Origin": "https://evil.example"}
        )
        shown = await client.post("/api/todo/show", headers=AUTH)
        unknown = await client.post("/api/todo/done", json={"item": "A99"}, headers=AUTH)
        malformed = await client.post("/api/todo/done", json={"what": 1}, headers=AUTH)
        done = await client.post("/api/todo/done", json={"item": "A19"}, headers=AUTH)
        hidden = await client.post("/api/todo/hide", headers=AUTH)
        shown_body, done_body, hidden_body = (
            await shown.json(),
            await done.json(),
            await hidden.json(),
        )
    finally:
        await client.close()
    assert refused == [403] * 5 and foreign.status == 403
    assert shown.status == 200 and shown_body["view"] == "todo"
    assert (unknown.status, malformed.status) == (404, 400)
    assert done.status == 200 and done_body["changed"] is True
    assert hidden_body == {"ok": True, "view": "items"}
