"""The page's JSON routes: /api/login, /api/state, /api/send and /api/action.

/api/send goes to the orchestrator; /api/action runs a button in the server itself.

The guard (server/security) has already checked Host, Origin and, except for
login, the X-Console-Token header.
"""

import json

from aiohttp import web

from signal_console.actions import SAVE_ACTIONS, ActionError, plan_action
from signal_console.orchestrator import RequestError, chat_request
from signal_console.server.action_runner import ActionBusy
from signal_console.server.routes.json_body import bad_request, read_json_object
from signal_console.server.security import LOGIN_PATH
from signal_console.server.services import SERVICES_KEY


def add_api_routes(app: web.Application) -> None:
    """Register the page's JSON routes."""
    app.router.add_post(LOGIN_PATH, login)
    app.router.add_get("/api/state", state)
    app.router.add_post("/api/send", send)
    app.router.add_post("/api/action", action)


async def login(request: web.Request) -> web.Response:
    """`{key}` (a one-time key from `console open`) -> 200 `{token}`, else 401.

    The page sends the token as X-Console-Token on every other /api call.
    """
    auth = request.app[SERVICES_KEY].auth
    key = (await read_json_object(request)).get("key")
    token = auth.log_in(key) if isinstance(key, str) else None
    if token is None:
        return web.json_response(
            {"error": "that login key is wrong, used or expired; run `console open` again"},
            status=401,
        )
    return web.json_response({"token": token})


async def state(request: web.Request) -> web.Response:
    """The orchestrator, voice and board status."""
    return web.json_response(await request.app[SERVICES_KEY].status.snapshot())


async def send(request: web.Request) -> web.Response:
    """`{text}` -> 202 `{id}`; the text goes to the orchestrator in the background."""
    services = request.app[SERVICES_KEY]
    try:
        console_request = chat_request((await read_json_object(request)).get("text"))
    except RequestError as error:
        raise bad_request(str(error)) from error
    return web.json_response({"id": services.dispatcher.submit(console_request)}, status=202)


async def action(request: web.Request) -> web.Response:
    """`{action, args?}` -> 202 `{id}`; the server runs the button itself, in the background.

    400 for an unknown action or a bad argument, 409 while an action sharing
    its lock (voice, or board) still runs. The result comes as `delivery` events.
    """
    services = request.app[SERVICES_KEY]
    body = await read_json_object(request)
    args = body.get("args") or {}
    if not isinstance(args, dict):
        raise bad_request("args must be a JSON object")
    # Only actions that name a save need the saves, and reading them costs a whiteboard request.
    # (A non-string action, e.g. a list, isn't hashable, so it's checked as a string first.)
    action_name = body.get("action")
    names_save = isinstance(action_name, str) and action_name in SAVE_ACTIONS
    saves = await services.status.saves() if names_save else {}
    try:
        plan = plan_action(action_name, args, saves)
    except ActionError as error:
        raise bad_request(str(error)) from error
    try:
        message_id = services.actions.submit(plan)
    except ActionBusy as error:
        raise web.HTTPConflict(
            text=json.dumps({"error": str(error)}), content_type="application/json"
        ) from error
    return web.json_response({"id": message_id}, status=202)
