"""aiohttp middlewares (loopback-only access, JSON API errors) and the no-cache header hook.

The daemon listens on 127.0.0.1, but a web page in the owner's browser can still
reach it. Two checks close that hole:
- Host must be a loopback name. This blocks DNS rebinding, where evil.example
  resolves to 127.0.0.1 and could read camera snapshots.
- Origin, when the browser sends one, must be a loopback origin. This blocks
  cross-site POSTs (drawing on the board) and cross-site WebSocket listeners.
"""

import logging
from collections.abc import Awaitable, Callable
from urllib.parse import urlsplit

from aiohttp import web

from whiteboard.display.scene import ItemNotFoundError, NightViewError, SceneError

log = logging.getLogger(__name__)

LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})
API_PREFIX = "/api/"

Handler = Callable[[web.Request], Awaitable[web.StreamResponse]]


@web.middleware
async def loopback_only(request: web.Request, handler: Handler) -> web.StreamResponse:
    """Reject requests whose Host or Origin isn't loopback (see the module docstring)."""
    host = (
        (request.host or "").rsplit(":", 1)[0]
        if not (request.host or "").startswith("[")
        else (request.host or "").split("]")[0] + "]"
    )
    if host.lower() not in LOOPBACK_HOSTS:
        raise web.HTTPForbidden(text="whiteboard daemon only accepts loopback Host headers")
    origin = request.headers.get("Origin")
    if origin is not None and (urlsplit(origin).hostname or "").lower() not in LOOPBACK_HOSTS:
        raise web.HTTPForbidden(text="whiteboard daemon rejects cross-origin requests")
    return await handler(request)


@web.middleware
async def json_errors(request: web.Request, handler: Handler) -> web.StreamResponse:
    """Turn scene errors into JSON `{ok: false, error}` responses on /api routes.

    SceneError becomes 400, ItemNotFoundError 404, and NightViewError 409 (a flash or
    highlight while the night view shows). An unexpected exception becomes 500 and is
    logged with its traceback.
    """
    if not request.path.startswith(API_PREFIX):
        return await handler(request)
    try:
        return await handler(request)
    except web.HTTPException:
        raise
    except ItemNotFoundError as error:
        return web.json_response({"ok": False, "error": str(error)}, status=404)
    except SceneError as error:
        return web.json_response({"ok": False, "error": str(error)}, status=400)
    except NightViewError as error:
        return web.json_response({"ok": False, "error": str(error)}, status=409)
    except Exception as error:
        log.exception("unhandled error in %s %s", request.method, request.path)
        return web.json_response({"ok": False, "error": f"internal error: {error}"}, status=500)


async def add_no_cache_header(request: web.Request, response: web.StreamResponse) -> None:
    """on_response_prepare hook: make the page revalidate everything, so it never runs
    stale board JS after an update. A signal (not a middleware) so it also covers
    static files and WebSocket handshakes, whose headers are sent inside the handler.
    """
    response.headers["Cache-Control"] = "no-cache"
