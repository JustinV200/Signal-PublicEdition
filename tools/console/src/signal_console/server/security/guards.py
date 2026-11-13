"""Request guard (Host, Origin, session token or local key) and security headers on every response.

The server listens on 127.0.0.1, but any web page the owner visits can send it
requests, so:
- Host must be this server's own 127.0.0.1:<port> or localhost:<port>. That
  blocks DNS rebinding (evil.example resolving to 127.0.0.1).
- An Origin, when sent, must be this server's own. Requests that change
  something (not GET/HEAD) from a page must send one; only the local routes
  (turn hook, CLI), which aren't browsers, may leave it out.
- /api/* needs a live session token in the X-Console-Token header (401
  without), except /api/login, and the local routes, which need the local key
  header instead. A header rather than a cookie, because browsers send
  127.0.0.1 cookies to every local port (see sessions.py).
No CORS headers are ever sent. Copied in spirit from tools/whiteboard's
loopback_only, request_guard and page_guard.
TODO: move these guards into a shared packages/ module with the whiteboard's.
"""

from collections.abc import Awaitable, Callable

from aiohttp import web

from signal_console.local_api import HOOK_TURN_PATH, LOGIN_KEY_PATH
from signal_console.paths import LOCAL_KEY_HEADER
from signal_console.server.security.sessions import (
    SESSION_TOKEN_HEADER,
    SessionAuth,
    secrets_match,
)

API_PREFIX = "/api/"
LOGIN_PATH = "/api/login"
LOCAL_PATHS = frozenset({HOOK_TURN_PATH, LOGIN_KEY_PATH})
SAFE_METHODS = frozenset({"GET", "HEAD"})
OWN_HOST_NAMES = ("127.0.0.1", "localhost")

# Vite builds load scripts and styles from files; inline styles are allowed because
# UI libraries commonly inject <style> tags. blob: images are the camera view's frames,
# which the page cuts out of its own fetched stream (never a remote URL).
CONTENT_SECURITY_POLICY = (
    "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data: blob:; font-src 'self'; connect-src 'self'; object-src 'none'; "
    "base-uri 'none'; form-action 'self'; frame-ancestors 'none'"
)

Handler = Callable[[web.Request], Awaitable[web.StreamResponse]]
Middleware = Callable[[web.Request, Handler], Awaitable[web.StreamResponse]]


def build_guard(auth: SessionAuth, local_key: str) -> Middleware:
    """Make the middleware that admits only this server's own page and local callers.

    Args:
        auth: Checks the page's session token.
        local_key: The secret the local routes require as X-Console-Key.

    Returns:
        An aiohttp middleware. Rejections are 403, or 401 for "not logged in",
        and close the connection.
    """

    @web.middleware
    async def guard(request: web.Request, handler: Handler) -> web.StreamResponse:
        own_hosts = _own_hosts(request)
        if request.host not in own_hosts:
            return _refuse(request, 403, "this server only answers to its own loopback address")
        refusal = _origin_refusal(request, own_hosts)
        if refusal is not None:
            return _refuse(request, 403, refusal)
        if not request.path.startswith(API_PREFIX) or request.path == LOGIN_PATH:
            return await handler(request)
        if request.path in LOCAL_PATHS:
            if not secrets_match(request.headers.get(LOCAL_KEY_HEADER, ""), local_key):
                return _refuse(request, 403, f"missing or wrong {LOCAL_KEY_HEADER} header")
        elif not auth.is_session_token(request.headers.get(SESSION_TOKEN_HEADER, "")):
            return _refuse(request, 401, "not logged in; run `console open`")
        return await handler(request)

    return guard


async def add_security_headers(request: web.Request, response: web.StreamResponse) -> None:
    """on_response_prepare hook: CSP and friends on everything, and no caching of /api."""
    response.headers["Content-Security-Policy"] = CONTENT_SECURITY_POLICY
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Cache-Control"] = (
        "no-store" if request.path.startswith(API_PREFIX) else "no-cache"
    )


def _own_hosts(request: web.Request) -> frozenset[str]:
    # The port this connection actually arrived on, so the guard needs no configuration.
    sockname = request.transport.get_extra_info("sockname") if request.transport else None
    if not sockname:
        return frozenset()
    return frozenset(f"{name}:{sockname[1]}" for name in OWN_HOST_NAMES)


def _origin_refusal(request: web.Request, own_hosts: frozenset[str]) -> str | None:
    origin = request.headers.get("Origin")
    if origin is not None and origin not in {f"http://{host}" for host in own_hosts}:
        return "cross-origin requests are refused"
    is_unsafe = request.method not in SAFE_METHODS
    if origin is None and is_unsafe and request.path not in LOCAL_PATHS:
        return "requests from the page must carry its Origin"
    return None


def _refuse(request: web.Request, status: int, reason: str) -> web.Response:
    # Closing stops a refused client reusing the keep-alive connection, e.g. to have
    # an unread body parsed as the next request.
    if request.path.startswith(API_PREFIX):
        response = web.json_response({"error": reason}, status=status)
    else:
        response = web.Response(status=status, text=reason)
    response.force_close()
    return response
