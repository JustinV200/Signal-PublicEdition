"""Routes for the board page itself: /board, /files (repo images) and the /ws WebSocket.

The static assets (/static/...) are added by app.create_app with aiohttp's
static handler, which already refuses paths outside STATIC_DIR.
"""

import json
import logging
from pathlib import Path

from aiohttp import WSMsgType, web

from whiteboard.display.scene import SceneError, resolve_image_path
from whiteboard.display.server.app_keys import BOARD_KEY

log = logging.getLogger(__name__)

STATIC_DIR: Path = Path(__file__).resolve().parents[1] / "static"
# Ping the page this often so a dead projector window is noticed and dropped.
WS_HEARTBEAT_S = 20.0

routes = web.RouteTableDef()


@routes.get("/board")
async def board_page(request: web.Request) -> web.FileResponse:
    """Serve the board page that the Edge kiosk shows on the projector."""
    return web.FileResponse(STATIC_DIR / "board.html")


@routes.get("/files")
async def repo_image(request: web.Request) -> web.FileResponse:
    """Serve a PNG/JPEG from inside the repo for `image` items: `/files?path=<repo path>`."""
    try:
        path = resolve_image_path(request.query.get("path", ""))
    except SceneError as error:
        raise web.HTTPNotFound(text=str(error)) from error
    return web.FileResponse(path)


@routes.get("/ws")
async def board_socket(request: web.Request) -> web.WebSocketResponse:
    """Push the scene, mode, TODO and idle data to a board page, then every change as it happens.

    Pages may send `{"type": "render_error", "id", "error"}` back; those are logged
    so a broken item shows up in the daemon log, not just on the projector.
    """
    board = request.app[BOARD_KEY]
    socket = web.WebSocketResponse(heartbeat=WS_HEARTBEAT_S)
    await socket.prepare(request)
    board.hub.add(socket)
    try:
        await socket.send_json(board.scene_message())
        await socket.send_json(board.mode_message())
        # Nothing is "newly done" for a page that just connected: no animation.
        await socket.send_json(board.todo_message())
        await socket.send_json(board.idle_message())
        async for message in socket:
            if message.type == WSMsgType.TEXT:
                _log_page_message(message.data)
    finally:
        board.hub.discard(socket)
    return socket


def _log_page_message(text: str) -> None:
    try:
        message = json.loads(text)
    except json.JSONDecodeError:
        log.warning("board page sent non-JSON text: %.200s", text)
        return
    if isinstance(message, dict) and message.get("type") == "render_error":
        log.warning(
            "board page failed to render item %s: %s", message.get("id"), message.get("error")
        )
    else:
        log.debug("board page says: %.200s", text)
