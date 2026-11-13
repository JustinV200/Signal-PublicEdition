"""The setup wizard's routes: POST /api/setup/run and POST /api/setup/terminal.

Like the buttons, these act directly on the owner's click in the logged-in page (the
guard has checked Host, Origin and X-Console-Token), never on a message. /run runs one
fixed setup CLI command (signal_console.setup_cli builds its argv) and streams its
output as NDJSON: `{"line": "..."}` per output line, then `{"exit": <code>}`.
"""

import contextlib
import json

from aiohttp import web

from signal_console.paths import REPO_ROOT
from signal_console.server.routes.json_body import bad_request, read_json_object
from signal_console.server.services import SERVICES_KEY
from signal_console.setup_cli import SetupBusy, SetupRequestError, build_call, open_terminal

NDJSON = "application/x-ndjson"


def add_setup_routes(app: web.Application) -> None:
    """Register the setup wizard's routes."""
    app.router.add_post("/api/setup/run", run_setup)
    app.router.add_post("/api/setup/terminal", open_setup_terminal)


async def run_setup(request: web.Request) -> web.StreamResponse:
    """`{command, ...}` -> 200 NDJSON stream of the CLI's lines and its exit code.

    400 for an unknown command or a bad field, 409 while another command that writes
    runs (read-only commands, such as list or status, run beside anything).
    The exit code follows the setup CLI: 0 done, 1 failed, 2 bad id, 3 needs the user.
    """
    runner = request.app[SERVICES_KEY].setup
    try:
        call = build_call(await read_json_object(request))
        if call.exclusive:
            runner.check_free()
    except SetupRequestError as error:
        raise bad_request(str(error)) from error
    except SetupBusy as error:
        raise web.HTTPConflict(
            text=json.dumps({"error": str(error)}), content_type="application/json"
        ) from error
    response = web.StreamResponse(headers={"Content-Type": NDJSON, "Cache-Control": "no-store"})
    await response.prepare(request)

    async def send(record: dict) -> None:
        await response.write((json.dumps(record) + "\n").encode("utf-8"))

    try:
        code = await runner.run(call, lambda line: send({"line": line}))
    except SetupBusy as error:  # lost a race with another click since check_free
        await send({"line": str(error)})
        code = 1
    # The page may have gone away; the command already finished and saved its progress.
    with contextlib.suppress(ConnectionError, RuntimeError):
        await send({"exit": code})
        await response.write_eof()
    return response


async def open_setup_terminal(request: web.Request) -> web.Response:
    """`{tool}` -> 200 `{ok}` after opening a terminal on `setup.ps1 <tool>`; 400 if it can't."""
    body = await read_json_object(request)
    try:
        open_terminal(REPO_ROOT, body.get("tool"))
    except (SetupRequestError, OSError) as error:
        raise bad_request(str(error)) from error
    return web.json_response({"ok": True})
