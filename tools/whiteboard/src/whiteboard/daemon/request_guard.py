"""CSRF guard for the daemon: /api/* needs the token, and /ws only accepts the board page's origin.

Any web page the owner visits can send requests to 127.0.0.1, so without this
it could draw on the board, clear it, take snapshots or recalibrate. The
token lives in .state/token, which pages can't read; the MCP server and CLI
send it as X-Signal-Token. Everything outside /api/ (the board page, /files,
/ws) needs display's page cookie instead (display/server/page_guard.py), and
/ws must also come from the daemon's own origin. display's loopback_only
middleware adds a Host check.
"""

import hmac
from collections.abc import Awaitable, Callable

from aiohttp import web

from whiteboard.daemon_client import TOKEN_HEADER

API_PREFIX = "/api/"
WEBSOCKET_PATH = "/ws"
OWN_HOSTS = ("127.0.0.1", "localhost")

Handler = Callable[[web.Request], Awaitable[web.StreamResponse]]
Middleware = Callable[[web.Request, Handler], Awaitable[web.StreamResponse]]


def own_origins(port: int) -> frozenset[str]:
    """The Origin values the board page sends when loaded from this daemon."""
    return frozenset(f"http://{host}:{port}" for host in OWN_HOSTS)


def build_request_guard(token: str, port: int) -> Middleware:
    """Make the middleware enforcing the token on /api/* and the origin on /ws.

    Args:
        token: The secret written to .state/token at startup.
        port: The daemon's port, which fixes its own origin.

    Returns:
        An aiohttp middleware. Rejections are 403 (JSON for /api/*).
    """
    allowed_origins = own_origins(port)
    expected_token = token.encode("utf-8")

    @web.middleware
    async def request_guard(request: web.Request, handler: Handler) -> web.StreamResponse:
        origin = request.headers.get("Origin")
        if request.path.startswith(API_PREFIX):
            # Defence in depth: a browser always sends Origin on a cross-site POST.
            if origin is not None and origin not in allowed_origins:
                return _api_forbidden("cross-origin requests are not allowed")
            supplied = request.headers.get(TOKEN_HEADER, "").encode("utf-8")
            if not hmac.compare_digest(supplied, expected_token):
                return _api_forbidden(f"missing or wrong {TOKEN_HEADER} header")
        elif request.path == WEBSOCKET_PATH and origin not in allowed_origins:
            response = web.Response(
                status=403, text="the board WebSocket only accepts the board page"
            )
            response.force_close()
            return response
        return await handler(request)

    return request_guard


def _api_forbidden(reason: str) -> web.Response:
    """A JSON 403 in the API's {ok, error} shape, closing the connection.

    Closing stops a rejected client from reusing the keep-alive connection, e.g.
    to send an unread request body that would be parsed as the next request.
    """
    response = web.json_response({"ok": False, "error": reason}, status=403)
    response.force_close()
    return response
