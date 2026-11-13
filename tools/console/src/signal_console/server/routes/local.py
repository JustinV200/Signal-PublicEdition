"""Routes for local processes, guarded by the local key instead of a session token.

POST /api/hook/turn: the turn hook reports a turn of the claimed orchestrator
starting, ending or going idle (`{phase, session_id, at, background_tasks?,
effort?, text?}`). An end's `text` is the turn's final message; it shows as a
"claude" message.
POST /api/local/login-key: `console open` gets a one-time page login key.
"""

import math
import time
from typing import Any

from aiohttp import web
from signal_modelchoice import EFFORT_LEVELS

from signal_console.local_api import HOOK_TURN_PATH, LOGIN_KEY_PATH
from signal_console.models import MAX_SESSION_ID_CHARS
from signal_console.server.events import new_event_id, now_iso
from signal_console.server.routes.json_body import bad_request, read_json_object
from signal_console.server.services import SERVICES_KEY
from signal_console.turns import TURN_PHASES, TurnReport

# A Stop can report any session effort, `max` included (settings files can't hold it).
REPORTED_EFFORTS = frozenset({*EFFORT_LEVELS, "max"})
# A hook stamps `at` before it posts, so a report from the future is bogus (clock skew aside).
MAX_FUTURE_S = 5.0


def add_local_routes(app: web.Application) -> None:
    """Register the local routes."""
    app.router.add_post(HOOK_TURN_PATH, hook_turn)
    app.router.add_post(LOGIN_KEY_PATH, login_key)


async def hook_turn(request: web.Request) -> web.Response:
    """A turn hook report: update the turn state, and show an end's final message (if any)."""
    services = request.app[SERVICES_KEY]
    body = await read_json_object(request)
    services.status.record_turn(parse_turn_report(body))
    text = body.get("text")
    # A turn can end without text (e.g. after an interrupted tool call, or an API error).
    if body["phase"] == "end" and isinstance(text, str) and text.strip():
        message = {"id": new_event_id(), "role": "claude", "text": text, "kind": "chat"}
        services.events.publish("message", message | {"at": now_iso()})
    return web.json_response({"ok": True})


def parse_turn_report(body: dict[str, Any]) -> TurnReport:
    """Check a turn hook body.

    Raises:
        web.HTTPBadRequest: A field is missing or has the wrong type or range.
    """
    phase, session_id, at = body.get("phase"), body.get("session_id"), body.get("at")
    background_tasks, effort = body.get("background_tasks"), body.get("effort")
    if phase not in TURN_PHASES:
        raise bad_request(f"phase must be one of {sorted(TURN_PHASES)}")
    if not isinstance(session_id, str) or not 0 < len(session_id) <= MAX_SESSION_ID_CHARS:
        raise bad_request("session_id must be a short string")
    # bool is an int subclass, and True isn't a time or a count.
    if isinstance(at, bool) or not isinstance(at, int | float) or not math.isfinite(at):
        raise bad_request("at must be epoch seconds")
    if at > time.time() + MAX_FUTURE_S:
        raise bad_request("at is in the future")
    is_count = isinstance(background_tasks, int) and not isinstance(background_tasks, bool)
    if background_tasks is not None and not (is_count and background_tasks >= 0):
        raise bad_request("background_tasks must be a count")
    # An effort level this console doesn't know only costs the strip's display, not the turn.
    if not (isinstance(effort, str) and effort in REPORTED_EFFORTS):
        effort = None
    return TurnReport(phase, session_id, float(at), background_tasks, effort)


async def login_key(request: web.Request) -> web.Response:
    """A fresh one-time login key for the page."""
    return web.json_response({"key": request.app[SERVICES_KEY].auth.issue_login_key()})
