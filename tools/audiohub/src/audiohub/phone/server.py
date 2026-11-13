"""`PhoneServer`: serves the phone page and its WebSocket on 127.0.0.1, for `audiohub run --phone`.

Tailscale Serve gives the phone HTTPS to this loopback port. Routes:
- `GET /?token=T`, the link `audiohub phone-link` prints. The right token sets
  the session cookie (HttpOnly, Secure, SameSite=Strict) and redirects to `/`.
  The redirect is a meta refresh rather than a 303, because a SameSite=Strict
  cookie isn't sent on a 303 in a navigation that began on another site, such
  as tapping the link in webmail.
- `GET /` and the page's scripts, cookie required.
- `GET /ws`, the phone socket (socket_handler.py); cookie and Origin required.

Every request must carry an allowed Host (auth.py). A refused request gets a
403 and its connection is closed. On start a fresh token is written to an
owner-only file (the kernel's token helpers) and removed again on close.
"""

import logging
from collections.abc import Awaitable, Callable
from pathlib import Path
from types import TracebackType
from typing import Self

from aiohttp import web

from audiohub.config import CACHE_DIR, PhoneSettings
from audiohub.kernel import create_token_file, remove_token_file, tokens_match

from .auth import (
    COOKIE_NAME,
    allowed_hostnames,
    is_host_allowed,
    is_origin_allowed,
    is_same_origin,
    is_session_cookie_valid,
    session_cookie_value,
)
from .link import PhoneLink
from .socket_handler import serve_phone_socket

logger = logging.getLogger(__name__)

DEFAULT_TOKEN_PATH = CACHE_DIR / "phone-token"
BIND_HOST = "127.0.0.1"
PAGE_DIR = Path(__file__).parent / "page"
# The page only ever GETs, so any request body is refused early.
MAX_REQUEST_BYTES = 1024
# How long close() waits for open requests once the phone socket is closed.
SHUTDOWN_TIMEOUT_S = 2.0
TOKEN_PARAM = "token"
# URL path -> (file in PAGE_DIR, content type).
PAGE_FILES = {
    "/": ("index.html", "text/html"),
    "/app.js": ("app.js", "text/javascript"),
    "/player.js": ("player.js", "text/javascript"),
    "/mic-worklet.js": ("mic-worklet.js", "text/javascript"),
}
SECURITY_HEADERS = {
    "Content-Security-Policy": (
        "default-src 'self'; style-src 'self' 'unsafe-inline'; "
        "base-uri 'none'; form-action 'none'; frame-ancestors 'none'"
    ),
    "Referrer-Policy": "no-referrer",
    "X-Content-Type-Options": "nosniff",
    "Cache-Control": "no-store",
}
LOGIN_REDIRECT_HTML = (
    '<!doctype html><meta charset="utf-8"><meta http-equiv="refresh" content="0;url=/">'
    "<title>audiohub</title>"
)
REFUSED_TEXT = "Forbidden. Open the link that `audiohub phone-link` prints on the PC."

Handler = Callable[[web.Request], Awaitable[web.StreamResponse]]


class PhoneServer:
    """The phone page server. Use as `async with`, or call `start` and `close`."""

    def __init__(
        self, link: PhoneLink, settings: PhoneSettings, token_path: Path = DEFAULT_TOKEN_PATH
    ) -> None:
        """Configure the server; nothing listens until `start`.

        Args:
            link: Where the phone socket is attached.
            settings: The port (0 picks a free one) and the allowed Tailscale hosts.
            token_path: Where to write the token. Tests use a temp file.
        """
        self._link = link
        self._settings = settings
        self._token_path = token_path
        self._allowed_hosts = allowed_hostnames(settings.allowed_hosts)
        self._token = ""
        self._pages: dict[str, bytes] = {}
        self._runner: web.AppRunner | None = None

    @property
    def port(self) -> int:
        """The port actually listened on. Raises RuntimeError before `start`."""
        if self._runner is None:
            raise RuntimeError("PhoneServer is not started")
        return self._runner.addresses[0][1]

    @property
    def token(self) -> str:
        """The secret in this run's token link (empty before `start`)."""
        return self._token

    async def start(self) -> None:
        """Listen on 127.0.0.1 and write a fresh token.

        Raises:
            OSError: If the port is taken, a page file is missing, or the token
                file can't be written (the listener is closed again).
        """
        self._pages = {
            path: (PAGE_DIR / name).read_bytes() for path, (name, _) in PAGE_FILES.items()
        }
        # access_log=None: aiohttp's access log would print the token link.
        runner = web.AppRunner(
            self._build_app(), access_log=None, shutdown_timeout=SHUTDOWN_TIMEOUT_S
        )
        await runner.setup()
        try:
            await web.TCPSite(runner, BIND_HOST, self._settings.port).start()
            self._token = create_token_file(self._token_path)
        except OSError:
            await runner.cleanup()
            raise
        self._runner = runner
        logger.info("phone page listening on %s:%d", BIND_HOST, self.port)

    async def close(self) -> None:
        """Remove the token file and stop serving, closing the phone socket."""
        if self._runner is None:
            return
        remove_token_file(self._token_path, self._token)
        self._token = ""
        # aiohttp waits for open handlers on cleanup, and the socket's runs until it closes.
        await self._link.disconnect()
        await self._runner.cleanup()
        self._runner = None

    async def __aenter__(self) -> Self:
        await self.start()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        await self.close()

    def _build_app(self) -> web.Application:
        app = web.Application(middlewares=[self._guard], client_max_size=MAX_REQUEST_BYTES)
        app.router.add_get("/ws", self._open_socket)
        for path in PAGE_FILES:
            app.router.add_get(path, self._serve_page)
        return app

    @web.middleware
    async def _guard(self, request: web.Request, handler: Handler) -> web.StreamResponse:
        """Refuse a bad Host on every request, and a missing cookie on all but the token link."""
        if not self._token:
            # Stopping (or not started): an empty token would match an empty one.
            return _refuse("the phone page server is not running")
        if not is_host_allowed(request.host, self._allowed_hosts):
            return _refuse("Host is not an allowed name")
        if _is_token_link(request):
            return self._log_in(request)
        if not is_session_cookie_valid(request.cookies.get(COOKIE_NAME), self._token):
            return _refuse(f"no valid session cookie for {request.path}")
        return await handler(request)

    def _log_in(self, request: web.Request) -> web.Response:
        if not tokens_match(request.query.get(TOKEN_PARAM), self._token):
            return _refuse("wrong token in the page link")
        response = web.Response(text=LOGIN_REDIRECT_HTML, content_type="text/html")
        response.headers.update(SECURITY_HEADERS)
        response.set_cookie(
            COOKIE_NAME,
            session_cookie_value(self._token),
            httponly=True,
            secure=True,
            samesite="Strict",
        )
        logger.info("phone page link opened; session cookie set")
        return response

    async def _serve_page(self, request: web.Request) -> web.Response:
        _, content_type = PAGE_FILES[request.path]
        response = web.Response(body=self._pages[request.path], content_type=content_type)
        response.headers.update(SECURITY_HEADERS)
        return response

    async def _open_socket(self, request: web.Request) -> web.StreamResponse:
        origin = request.headers.get("Origin")
        if not is_origin_allowed(origin, self._allowed_hosts):
            return _refuse("WebSocket Origin is not an allowed host")
        if not is_same_origin(origin, request.host):
            return _refuse("WebSocket Origin is not this page's origin")
        return await serve_phone_socket(request, self._link)


def _is_token_link(request: web.Request) -> bool:
    return request.path == "/" and TOKEN_PARAM in request.query


def _refuse(reason: str) -> web.Response:
    """A 403 that also closes the connection, so a probing client must reconnect."""
    logger.warning("refused a phone page request: %s", reason)
    response = web.Response(status=403, text=REFUSED_TEXT)
    response.force_close()
    return response
