"""System's device routes: GET /api/devices (rows and away mode) and POST /api/away (the toggle).

The guard has already checked Host, Origin and the X-Console-Token header.
GET is a read like /api/state. POST /api/away is the one console control
that acts directly instead of asking the orchestrator: it's the owner's own
Away/Here toggle (see signal_console.away).
"""

import asyncio
from datetime import datetime

from aiohttp import web
from signal_brief import BriefLogError

from signal_console.away import away_payload, set_away
from signal_console.server.routes.json_body import bad_request, read_json_object
from signal_console.server.services import SERVICES_KEY


def add_devices_routes(app: web.Application) -> None:
    """Register GET /api/devices and POST /api/away."""
    app.router.add_get("/api/devices", devices)
    app.router.add_post("/api/away", away)


async def devices(request: web.Request) -> web.Response:
    """`{devices: [row], away: {state, endsAt, note} | null}`; away is null if unreadable."""
    services = request.app[SERVICES_KEY]
    rows = await services.devices.rows(services.status.voice_status())
    try:
        away_block = await asyncio.to_thread(away_payload, services.brief_paths, _now())
    except BriefLogError:
        away_block = None
    return web.json_response({"devices": rows, "away": away_block})


async def away(request: web.Request) -> web.Response:
    """`{on: bool, until?: str}` -> the away block after the change; 400 for a bad end."""
    services = request.app[SERVICES_KEY]
    body = await read_json_object(request)
    is_on, until = body.get("on"), body.get("until", "")
    if not isinstance(is_on, bool) or not isinstance(until, str):
        raise bad_request("send {on: true|false, until?: text}")
    try:
        block = await asyncio.to_thread(set_away, services.brief_paths, _now(), is_on, until)
    except ValueError as error:
        raise bad_request(str(error)) from error
    except BriefLogError as error:
        return web.json_response(
            {"error": f"couldn't save whether you're away: {error}"}, status=503
        )
    return web.json_response(block)


def _now() -> datetime:
    return datetime.now().astimezone()
