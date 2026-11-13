"""create_app: build the daemon's aiohttp application around a BoardController.

The daemon (cli serve) creates the controller, passes the camera hooks, and runs
the returned app on 127.0.0.1. Tests use the same factory with aiohttp's test client.
"""

from aiohttp import web

from whiteboard.display.server import api_routes, page_routes
from whiteboard.display.server.app_keys import (
    BOARD_KEY,
    HOOKS_KEY,
    CalibrateHook,
    Hooks,
    LookHook,
    StatusHook,
)
from whiteboard.display.server.board import BoardController
from whiteboard.display.server.middlewares import add_no_cache_header, json_errors, loopback_only
from whiteboard.display.server.page_guard import build_page_guard


def create_app(
    board: BoardController,
    *,
    look: LookHook | None = None,
    calibrate: CalibrateHook | None = None,
    status: StatusHook | None = None,
    page_token: str | None = None,
) -> web.Application:
    """Build the HTTP/WebSocket app: /board, /static, /files, /ws and the /api routes.

    Args:
        board: The controller holding the scene, mode and connected pages.
        look: `async look(clean) -> {png_path, width, height, ...}` for POST /api/look.
        calibrate: `async calibrate() -> {ok, error?, reprojection_error_px}`, for
            POST /api/calibrate.
        status: `async status() -> dict` merged into GET /api/status.
        page_token: The daemon's token. When given, everything outside /api/ needs
            the page cookie that `/board?token=<page_token>` sets (see page_guard.py).
            The daemon always passes it; only tests leave the page routes open.

    Returns:
        The aiohttp Application, ready for `web.run_app` or an AppRunner.
    """
    middlewares = [loopback_only, json_errors]
    if page_token is not None:
        middlewares.insert(1, build_page_guard(page_token))
    app = web.Application(middlewares=middlewares)
    app[BOARD_KEY] = board
    app[HOOKS_KEY] = Hooks(look=look, calibrate=calibrate, status=status)
    app.on_response_prepare.append(add_no_cache_header)
    app.on_shutdown.append(_close_pages)
    app.add_routes(api_routes.routes)
    app.add_routes(page_routes.routes)
    app.router.add_static("/static/", page_routes.STATIC_DIR)
    return app


async def _close_pages(app: web.Application) -> None:
    # Open WebSockets would otherwise hold graceful shutdown until they time out.
    await app[BOARD_KEY].hub.close_all()
