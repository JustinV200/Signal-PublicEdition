"""POST /api/models: the owner's model or effort pick from the model strip.

Like POST /api/away, this acts directly instead of asking the orchestrator,
and only on the owner's click: it writes the `model` or `effortLevel` key of
.claude/settings.local.json (for new Signal sessions) or voice's
brain-choice.json, nothing else (see signal_console.models). The guard has
already checked Host, Origin and the X-Console-Token header.
"""

import asyncio

from aiohttp import web
from signal_jsonstate import StateFileError

from signal_console.models import PickError, SettingsWriteError, apply_pick
from signal_console.server.routes.json_body import bad_request, read_json_object
from signal_console.server.services import SERVICES_KEY

HTTP_CONFLICT = 409


def add_models_route(app: web.Application) -> None:
    """Register POST /api/models."""
    app.router.add_post("/api/models", pick_model)


async def pick_model(request: web.Request) -> web.Response:
    """`{target, field, index}` -> 200 `{ok}`; 400 for a bad pick, 409 when it can't be written.

    `index` points into `models.choices[target][field]` of /api/state. The new
    state is published at once, so the strip shows the pick without waiting a poll.
    """
    services = request.app[SERVICES_KEY]
    body = await read_json_object(request)
    try:
        await asyncio.to_thread(
            apply_pick, services.models, body.get("target"), body.get("field"), body.get("index")
        )
    except PickError as error:
        raise bad_request(str(error)) from error
    except (SettingsWriteError, StateFileError) as error:
        return web.json_response({"error": str(error)}, status=HTTP_CONFLICT)
    await services.status.refresh(read_boards=False)
    return web.json_response({"ok": True})
