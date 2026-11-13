"""API round trip and WebSocket broadcast, through aiohttp's test client."""

import pytest
import pytest_asyncio
from aiohttp.test_utils import TestClient, TestServer

from whiteboard.display.scene import SceneStore
from whiteboard.display.server import BoardController, create_app

TEXT_ITEM = {
    "id": "t1",
    "kind": "text",
    "x": 10,
    "y": 20,
    "w": 300,
    "h": 60,
    "content": "Signal whiteboard online",
}


@pytest_asyncio.fixture
async def client(tmp_path):
    async def look(clean: bool) -> dict:
        return {"png_path": "snap.png", "width": 1280, "height": 720, "clean": clean}

    board = BoardController(SceneStore(tmp_path / "scene.json"))
    async with TestClient(TestServer(create_app(board, look=look))) as test_client:
        yield test_client


@pytest.mark.asyncio
async def test_item_round_trip(client: TestClient) -> None:
    created = await (await client.post("/api/items", json=TEXT_ITEM)).json()
    assert created["id"] == "t1"

    patched = await client.patch("/api/items/t1", json={"x": 50, "style": {"color": "#ff0"}})
    assert (await patched.json())["item"]["x"] == 50

    scene = await (await client.get("/api/scene")).json()
    assert [item["id"] for item in scene["items"]] == ["t1"]
    assert scene["items"][0]["style"]["color"] == "#ff0"

    assert (await client.delete("/api/items/t1")).status == 200
    assert (await client.delete("/api/items/t1")).status == 404
    assert (await client.post("/api/items", json={"kind": "nope"})).status == 400


@pytest.mark.asyncio
async def test_fit_sets_logical_stage_and_clears(client: TestClient) -> None:
    quad = [[100, 50], [1200, 60], [1180, 700], [90, 690]]
    assert (await client.post("/api/fit", json={"quad": quad})).status == 200
    stage = (await (await client.get("/api/status")).json())["stage"]
    assert stage["fitted"] and stage["height"] == 720 and len(stage["matrix3d"]) == 16

    await client.post("/api/fit", json={"quad": None})
    stage = (await (await client.get("/api/status")).json())["stage"]
    assert (stage["fitted"], stage["width"], stage["height"]) == (False, 1280, 720)


@pytest.mark.asyncio
async def test_look_hook_and_missing_calibrate_hook(client: TestClient) -> None:
    looked = await (await client.post("/api/look", json={"clean": False})).json()
    assert looked["png_path"] == "snap.png" and looked["clean"] is False
    assert (await client.post("/api/calibrate")).status == 503


@pytest.mark.asyncio
async def test_websocket_gets_state_then_broadcasts(client: TestClient) -> None:
    socket = await client.ws_connect("/ws")
    assert (await socket.receive_json())["type"] == "scene"
    assert (await socket.receive_json())["mode"] == "normal"
    # A page that just connected gets the TODO data with nothing to animate.
    assert await socket.receive_json() == {"type": "todo", "todo": None, "newly_done": []}
    assert await socket.receive_json() == {"type": "idle", "idle": None}

    await client.post("/api/items", json=TEXT_ITEM)
    update = await socket.receive_json()
    assert update["type"] == "scene" and update["items"][0]["content"] == TEXT_ITEM["content"]

    marker = {"url": "data:image/png;base64,AAAA", "x": 0, "y": 0, "w": 100, "h": 100}
    await client.post("/api/mode", json={"mode": "pattern", "markers": [marker]})
    mode = await socket.receive_json()
    assert mode["mode"] == "pattern" and mode["markers"] == [marker]

    await client.post("/api/highlight", json={"x": 1, "y": 2, "w": 3, "h": 4})
    assert (await socket.receive_json())["type"] == "highlight"
    await socket.close()


@pytest.mark.asyncio
async def test_rejects_cross_origin_and_rebound_host(client: TestClient) -> None:
    evil_origin = await client.post("/api/clear", headers={"Origin": "https://evil.example"})
    assert evil_origin.status == 403
    rebound = await client.get("/api/scene", headers={"Host": "evil.example:8770"})
    assert rebound.status == 403
