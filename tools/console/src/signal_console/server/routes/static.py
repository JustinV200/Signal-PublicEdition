"""Serve the built frontend (tools/console/web/dist) with SPA fallback, or a placeholder.

Any path that isn't a file in dist/ gets index.html, so client-side routes
work. Until the frontend is built, every page path gets a short placeholder.
The page itself is public (on loopback, behind the Host check); its data
needs a session token.

A request path is checked as text before it touches the filesystem: anything
that could name a file outside dist/ (a backslash, a drive colon, NUL, an
absolute path or a `..` segment) gets index.html without a lookup. A path
that passes is then resolved, which follows symlinks, and must still be inside dist/.
"""

import mimetypes
from pathlib import Path

from aiohttp import web

# Windows can map .js to text/plain in the registry, which nosniff then refuses to run.
mimetypes.add_type("text/javascript", ".js")
mimetypes.add_type("text/javascript", ".mjs")
mimetypes.add_type("text/css", ".css")

UNSAFE_PATH_CHARS = ("\\", ":", "\0")
PARENT_SEGMENT = ".."

PLACEHOLDER_HTML = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>Signal console</title></head>
<body style="font-family: sans-serif; margin: 3rem;">
<h1>Signal console</h1>
<p>The console UI isn't built yet. Build it in <code>tools/console/web</code>
(it goes to <code>web/dist</code>), then reload this page.</p>
</body></html>
"""


def add_static_routes(app: web.Application, web_dir: Path) -> None:
    """Register the catch-all page route (add it after the /api routes)."""
    root = web_dir.resolve()

    async def page(request: web.Request) -> web.StreamResponse:
        if request.path.startswith("/api/"):
            raise web.HTTPNotFound()
        index = root / "index.html"
        if not index.is_file():
            return web.Response(text=PLACEHOLDER_HTML, content_type="text/html")
        return web.FileResponse(_file_in(root, request.match_info["tail"]) or index)

    app.router.add_get("/{tail:.*}", page)


def _file_in(root: Path, tail: str) -> Path | None:
    if not _is_plain_relative(tail):
        return None
    candidate = (root / tail).resolve()
    # Containment first, so is_file() never stats a path outside dist/.
    if candidate.is_relative_to(root) and candidate.is_file():
        return candidate
    return None


def _is_plain_relative(tail: str) -> bool:
    # Backslashes and colons are Windows separators and drive / stream markers.
    if any(char in tail for char in UNSAFE_PATH_CHARS):
        return False
    return not tail.startswith("/") and PARENT_SEGMENT not in tail.split("/")
