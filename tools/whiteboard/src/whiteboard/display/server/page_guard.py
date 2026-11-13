"""Cookie guard for the board page: everything outside /api/ needs the page cookie.

That covers /board, /static, /files (camera snapshots) and /ws (the scene feed).
The daemon's own middleware guards /api/* with its token header.

The kiosk opens `/board?token=<daemon token>`. That sets an HttpOnly,
SameSite=Strict cookie and redirects to plain /board, so the token leaves the
address bar and the page's scripts never see it. Other sites can neither read
the cookie nor make the browser send it (SameSite=Strict). The cookie holds an
HMAC of the token rather than the token, so it can't be replayed as the API token.
"""

import hashlib
import hmac
from collections.abc import Awaitable, Callable

from aiohttp import web

COOKIE_NAME = "whiteboard_page"
TOKEN_QUERY = "token"
BOARD_PATH = "/board"
API_PREFIX = "/api/"
_COOKIE_CONTEXT = b"whiteboard board page cookie"

Handler = Callable[[web.Request], Awaitable[web.StreamResponse]]
Middleware = Callable[[web.Request, Handler], Awaitable[web.StreamResponse]]


def page_cookie_value(token: str) -> str:
    """The cookie value for a daemon token: an HMAC of it, never the token itself."""
    return hmac.new(token.encode("utf-8"), _COOKIE_CONTEXT, hashlib.sha256).hexdigest()


def build_page_guard(token: str) -> Middleware:
    """Make the middleware that requires the page cookie outside /api/.

    Args:
        token: The daemon's API token; the kiosk URL carries it once as ?token=.

    Returns:
        An aiohttp middleware. Missing or wrong cookies and tokens get 403.
    """
    expected_cookie = page_cookie_value(token).encode("utf-8")
    expected_token = token.encode("utf-8")

    @web.middleware
    async def page_guard(request: web.Request, handler: Handler) -> web.StreamResponse:
        if request.path.startswith(API_PREFIX):
            return await handler(request)
        if request.path == BOARD_PATH and TOKEN_QUERY in request.query:
            supplied_token = request.query[TOKEN_QUERY].encode("utf-8")
            if not hmac.compare_digest(supplied_token, expected_token):
                raise web.HTTPForbidden(text="wrong board token")
            return _start_page_session(expected_cookie.decode("utf-8"))
        supplied_cookie = request.cookies.get(COOKIE_NAME, "").encode("utf-8")
        if not hmac.compare_digest(supplied_cookie, expected_cookie):
            raise web.HTTPForbidden(text="open the board from the daemon's kiosk link")
        return await handler(request)

    return page_guard


def _start_page_session(cookie_value: str) -> web.Response:
    # Redirect to plain /board so the token doesn't stay in the URL or history.
    response = web.Response(status=302, headers={"Location": BOARD_PATH})
    response.set_cookie(COOKIE_NAME, cookie_value, httponly=True, samesite="Strict", path="/")
    return response
