"""Serve the built frontend (tools/console/web/dist) with SPA fallback, or a placeholder.

Any path that isn't a file in dist/ gets index.html, so client-side routes
work. Until the frontend is built, every page path gets a short placeholder
naming the build command (setup builds it; `console open` never does), with a
Copy button whose script this module serves too. The page itself is public (on
loopback, behind the Host check); its data needs a session token.

A request path is checked as text before it touches the filesystem: anything
that could name a file outside dist/ (a backslash, a drive colon, NUL, an
absolute path or a `..` segment) gets index.html without a lookup. A path
that passes is then resolved, which follows symlinks, and must still be inside dist/.
"""

import html
import mimetypes
from pathlib import Path

from aiohttp import web

from signal_console.health import SETUP_COMMAND

# Windows can map .js to text/plain in the registry, which nosniff then refuses to run.
mimetypes.add_type("text/javascript", ".js")
mimetypes.add_type("text/javascript", ".mjs")
mimetypes.add_type("text/css", ".css")

UNSAFE_PATH_CHARS = ("\\", ":", "\0")
PARENT_SEGMENT = ".."

# The placeholder's Copy button. The CSP allows only this server's own scripts and dist/
# is missing, so the server serves this one itself, at this path.
PLACEHOLDER_SCRIPT_PATH = "placeholder-copy.js"
PLACEHOLDER_HTML = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>Signal console</title>
<script src="/{PLACEHOLDER_SCRIPT_PATH}" defer></script></head>
<body style="font-family: sans-serif; margin: 3rem;">
<h1>Signal console</h1>
<p>The console's page isn't built yet. Build it by running this from the repo root:</p>
<p><code id="command">{html.escape(SETUP_COMMAND)}</code>
<button type="button" id="copy">Copy</button> <span id="copied" role="status"></span></p>
<p>Then run <code>console open</code> again.</p>
</body></html>
"""
PLACEHOLDER_SCRIPT = """// Copy the build command on the "page isn't built" placeholder.
document.getElementById("copy").addEventListener("click", async () => {
  const status = document.getElementById("copied");
  try {
    await navigator.clipboard.writeText(document.getElementById("command").textContent);
    status.textContent = "Copied";
  } catch {
    status.textContent = "Couldn't copy: select the command and copy it yourself";
  }
});
"""


def add_static_routes(app: web.Application, web_dir: Path) -> None:
    """Register the catch-all page route (add it after the /api routes)."""
    root = web_dir.resolve()

    async def page(request: web.Request) -> web.StreamResponse:
        if request.path.startswith("/api/"):
            raise web.HTTPNotFound()
        index = root / "index.html"
        if not index.is_file():
            return _placeholder(request.match_info["tail"])
        return web.FileResponse(_file_in(root, request.match_info["tail"]) or index)

    app.router.add_get("/{tail:.*}", page)


def _placeholder(tail: str) -> web.Response:
    # Until dist/ is built: the Copy script at its own path, the placeholder page everywhere else.
    if tail == PLACEHOLDER_SCRIPT_PATH:
        return web.Response(text=PLACEHOLDER_SCRIPT, content_type="text/javascript")
    return web.Response(text=PLACEHOLDER_HTML, content_type="text/html")


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
