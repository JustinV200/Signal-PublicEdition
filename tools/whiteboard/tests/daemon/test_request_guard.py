"""The CSRF guard on display's real app: /api/* needs the token, /ws the board page's origin."""

import socket

import aiohttp
import pytest
from aiohttp.test_utils import TestClient, TestServer

from whiteboard.daemon.request_guard import build_request_guard
from whiteboard.display.scene import SceneStore
from whiteboard.display.server import BoardController, create_app

pytestmark = pytest.mark.asyncio

TOKEN = "s3cret"


async def guarded_client(tmp_path) -> TestClient:
    """display's app with the guard installed, served on a free loopback port."""
    # The guard needs the port to know its own origin, so pick one before starting.
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    app = create_app(BoardController(SceneStore(tmp_path / "scene.json")))
    app.middlewares.insert(0, build_request_guard(TOKEN, port))
    client = TestClient(TestServer(app, host="127.0.0.1", port=port))
    await client.start_server()
    return client


async def test_api_requests_need_the_right_token_and_no_foreign_origin(tmp_path) -> None:
    client = await guarded_client(tmp_path)
    try:
        missing = await client.post("/api/clear")
        missing_body = await missing.json()
        wrong = await client.post("/api/clear", headers={"X-Signal-Token": "nope"})
        foreign = await client.post(
            "/api/clear", headers={"X-Signal-Token": TOKEN, "Origin": "https://evil.example"}
        )
        allowed = await client.post("/api/clear", headers={"X-Signal-Token": TOKEN})
    finally:
        await client.close()
    assert [missing.status, wrong.status, foreign.status] == [403, 403, 403]
    assert missing_body["ok"] is False
    assert allowed.status == 200


async def test_websocket_only_accepts_the_board_page_origin(tmp_path) -> None:
    client = await guarded_client(tmp_path)
    own_origin = f"http://127.0.0.1:{client.port}"
    try:
        with pytest.raises(aiohttp.WSServerHandshakeError) as rejected:
            await client.ws_connect(
                "/ws", headers={"Origin": f"http://localhost:{client.port + 1}"}
            )
        socket = await client.ws_connect("/ws", headers={"Origin": own_origin})
        first_message = await socket.receive_json()
        await socket.close()
    finally:
        await client.close()
    assert rejected.value.status == 403
    assert first_message["type"] == "scene"
