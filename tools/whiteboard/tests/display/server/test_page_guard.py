"""The board page cookie: /files and /ws need it, and only /board?token=<token> hands it out."""

from pathlib import Path

import aiohttp
import pytest
import pytest_asyncio
from aiohttp.test_utils import TestClient, TestServer

from whiteboard.display.scene import SceneStore
from whiteboard.display.server import BoardController, create_app

TOKEN = "daemon-token"
SNAPSHOT = "/files?path=tools/whiteboard/.state/snapshots/x.png"


@pytest_asyncio.fixture
async def client(tmp_path):
    board = BoardController(SceneStore(tmp_path / "scene.json"))
    async with TestClient(TestServer(create_app(board, page_token=TOKEN))) as test_client:
        yield test_client


@pytest.mark.asyncio
async def test_files_and_ws_need_the_cookie(client: TestClient) -> None:
    assert (await client.get(SNAPSHOT)).status == 403
    assert (await client.get("/board?token=wrong")).status == 403
    with pytest.raises(aiohttp.WSServerHandshakeError):
        await client.ws_connect("/ws")


@pytest.mark.asyncio
async def test_token_link_sets_strict_cookie_then_page_works(client: TestClient) -> None:
    login = await client.get(f"/board?token={TOKEN}", allow_redirects=False)
    assert login.status == 302 and login.headers["Location"] == "/board"
    cookie = login.headers["Set-Cookie"]
    assert "HttpOnly" in cookie and "SameSite=Strict" in cookie and TOKEN not in cookie

    assert (await client.get("/board")).status == 200
    socket = await client.ws_connect("/ws")
    assert (await socket.receive_json())["type"] == "scene"
    await socket.close()
    # With the cookie, a missing snapshot is a plain 404, not a 403.
    assert (await client.get(SNAPSHOT)).status == 404


@pytest.mark.asyncio
async def test_unc_path_via_files_never_touches_disk(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    await client.get(f"/board?token={TOKEN}")
    touched: list[Path] = []
    monkeypatch.setattr(Path, "resolve", lambda self, *args, **kwargs: touched.append(self))
    response = await client.get("/files", params={"path": r"\\attacker\share\x.png"})
    assert response.status == 404 and touched == []
