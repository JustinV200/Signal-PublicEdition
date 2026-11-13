"""A local HTTP server for browser tests.

Serves tests/fixtures/*.html (with {{PORT}} replaced by the live port), plus:
- /redirect?to=<host>  -> 302 to http://<host>:<port>/plain.html
- /pixel.png           -> a 1x1 PNG
- /report.pdf          -> a small two-page PDF, served inline (not as an attachment)
- /slow?ms=<delay>     -> plain.html after `delay` ms, so a navigation commits late
- /status?code=<code>  -> an empty response with that status (e.g. 204, which never commits)
- /download?name=<file name>&kb=<size> -> an attachment of `kb` KiB of "x"
  (default 1), sent in chunks with short pauses, so a size cap can catch it mid-way
- POST /posted         -> a page saying "posted", and the request recorded in
  `posts`, so a test can count form resubmissions
- /needs-login?login=<host>[&noservice=1] -> plain.html once the request carries
  the cookie visit-session=1, else a 302 to http://<host>:<port>/login.html with a
  `service` parameter pointing back here (left out with noservice), like Moodle's
  redirect to CAS (visit mode tests)
Every request's Host header and path is recorded in `hits`, so tests can prove
a blocked request never reached the server.

Tests address it as http://<name>.localhost:<port>/; Chromium resolves any
*.localhost name to loopback, so no DNS setup is needed.
"""

import base64
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, urlsplit

from support.local_files import make_pdf

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures"
DOWNLOAD_CHUNK = b"x" * 1024 * 64
DOWNLOAD_PAUSE_S = 0.02
PIXEL_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
)


class FixtureServer:
    """Threaded HTTP server bound to 127.0.0.1 on a free port."""

    def __init__(self) -> None:
        self.hits: list[str] = []
        self.posts: list[str] = []
        handler = _make_handler(self)
        self._server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        self.port = self._server.server_address[1]
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._server.shutdown()
        self._server.server_close()

    def url(self, host: str, path: str) -> str:
        return f"http://{host}:{self.port}{path}"

    def hosts_hit(self) -> set[str]:
        return {hit.split(":", 1)[0] for hit in self.hits}


def _make_handler(owner: FixtureServer) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args: object) -> None:
            """Keep test output quiet."""

        def do_GET(self) -> None:
            owner.hits.append(f"{self.headers.get('Host', '')}{self.path}")
            parts = urlsplit(self.path)
            if parts.path == "/redirect":
                target = parse_qs(parts.query)["to"][0]
                self._send(302, b"", {"Location": f"http://{target}:{owner.port}/plain.html"})
            elif parts.path == "/needs-login":
                self._needs_login(parse_qs(parts.query))
            elif parts.path == "/download":
                self._download(parse_qs(parts.query))
            elif parts.path == "/slow":
                time.sleep(int(parse_qs(parts.query)["ms"][0]) / 1000)
                self._serve_fixture("plain.html")
            elif parts.path == "/status":
                self._send(int(parse_qs(parts.query)["code"][0]), b"", {})
            elif parts.path == "/pixel.png":
                self._send(200, PIXEL_PNG, {"Content-Type": "image/png"})
            elif parts.path == "/report.pdf":
                pdf = make_pdf(["first page text", "second page text"])
                self._send(200, pdf, {"Content-Type": "application/pdf"})
            else:
                self._serve_fixture(parts.path.lstrip("/"))

        def do_POST(self) -> None:
            owner.posts.append(f"{self.headers.get('Host', '')}{self.path}")
            self.rfile.read(int(self.headers.get("Content-Length", "0")))
            body = b"<!doctype html><title>Posted</title><p>posted</p>"
            self._send(200, body, {"Content-Type": "text/html; charset=utf-8"})

        def _needs_login(self, query: dict[str, list[str]]) -> None:
            if "visit-session=1" in self.headers.get("Cookie", ""):
                self._serve_fixture("plain.html")
                return
            login = f"http://{query['login'][0]}:{owner.port}/login.html"
            back = quote(f"http://{self.headers.get('Host', '')}{self.path}", safe="")
            location = login if "noservice" in query else f"{login}?service={back}"
            self._send(302, b"", {"Location": location})

        def _download(self, query: dict[str, list[str]]) -> None:
            size = int(query.get("kb", ["1"])[0]) * 1024
            name = query["name"][0].replace('"', "")
            self.send_response(200)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Content-Disposition", f'attachment; filename="{name}"')
            self.send_header("Content-Length", str(size))
            self.end_headers()
            try:
                while size > 0:
                    self.wfile.write(DOWNLOAD_CHUNK[:size])
                    size -= len(DOWNLOAD_CHUNK)
                    time.sleep(DOWNLOAD_PAUSE_S)
            except ConnectionError:
                pass  # the browser cancelled it (the size cap test)

        def _serve_fixture(self, name: str) -> None:
            path = FIXTURES_DIR / name
            if not name or not path.is_file():
                self._send(404, b"not found", {"Content-Type": "text/plain"})
                return
            body = path.read_text(encoding="utf-8").replace("{{PORT}}", str(owner.port))
            self._send(200, body.encode("utf-8"), {"Content-Type": "text/html; charset=utf-8"})

        def _send(self, status: int, body: bytes, headers: dict[str, str]) -> None:
            self.send_response(status)
            for name, value in headers.items():
                self.send_header(name, value)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    return Handler
