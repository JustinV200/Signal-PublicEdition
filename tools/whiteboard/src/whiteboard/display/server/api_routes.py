"""The JSON API under /api, used by the MCP server and the CLI.

Every response is a JSON object with `ok`. Validation errors are 400, unknown
item ids 404, a flash or highlight while the night view shows 409 (see
middlewares.json_errors), and camera endpoints without a daemon hook 503.
"""

import dataclasses
from datetime import datetime

from aiohttp import web

from whiteboard.display.scene import item_from_dict, item_to_dict, scene_to_dict
from whiteboard.display.server.app_keys import BOARD_KEY, HOOKS_KEY
from whiteboard.display.server.requests import (
    parse_fit,
    parse_highlight,
    parse_look,
    parse_mode,
    parse_night,
    read_json_object,
)

routes = web.RouteTableDef()

_NO_CAMERA = "the camera isn't available in this daemon"


@routes.get("/api/scene")
async def get_scene(request: web.Request) -> web.Response:
    """Return every item, the board quad and the stage geometry."""
    board = request.app[BOARD_KEY]
    return web.json_response({"ok": True, **scene_to_dict(board.scene), "stage": board.stage()})


@routes.post("/api/items")
async def put_item(request: web.Request) -> web.Response:
    """Create an item, or replace the one with the same id. Returns its id."""
    item = item_from_dict(await read_json_object(request))
    await request.app[BOARD_KEY].put_item(item)
    return web.json_response({"ok": True, "id": item.id, "item": item_to_dict(item)})


@routes.patch("/api/items/{item_id}")
async def patch_item(request: web.Request) -> web.Response:
    """Move, resize, restyle or re-content one item."""
    changes = await read_json_object(request)
    item = await request.app[BOARD_KEY].patch_item(request.match_info["item_id"], changes)
    return web.json_response({"ok": True, "id": item.id, "item": item_to_dict(item)})


@routes.delete("/api/items/{item_id}")
async def delete_item(request: web.Request) -> web.Response:
    """Remove one item."""
    await request.app[BOARD_KEY].remove_item(request.match_info["item_id"])
    return web.json_response({"ok": True})


@routes.post("/api/clear")
async def clear(request: web.Request) -> web.Response:
    """Remove every item. The board fit stays."""
    await request.app[BOARD_KEY].clear()
    return web.json_response({"ok": True})


@routes.post("/api/highlight")
async def highlight(request: web.Request) -> web.Response:
    """Flash a bright box: `{x, y, w, h, seconds?}` in stage pixels."""
    await request.app[BOARD_KEY].highlight(parse_highlight(await read_json_object(request)))
    return web.json_response({"ok": True})


@routes.post("/api/mode")
async def set_mode(request: web.Request) -> web.Response:
    """Switch the display mode: `{mode, markers?}` (markers only matter for pattern)."""
    mode, markers = parse_mode(await read_json_object(request))
    await request.app[BOARD_KEY].set_mode(mode, markers)
    return web.json_response({"ok": True, "mode": mode})


@routes.post("/api/fit")
async def set_fit(request: web.Request) -> web.Response:
    """Set the board fit `{quad: [[x, y] x4]}` in projector pixels, or clear it with null."""
    board = request.app[BOARD_KEY]
    await board.set_fit(parse_fit(await read_json_object(request)))
    return web.json_response({"ok": True, "stage": board.stage()})


@routes.post("/api/night/show")
async def night_show(request: web.Request) -> web.Response:
    """Show the night view (sleep mode): `{seed?}`, what tools/sleepmode sends.

    Returns `{ok, view: "night", seed, previous_view}`. Already showing, only the
    seed changes; previous_view stays the view from before the night.
    """
    seed = parse_night(await read_json_object(request), datetime.now())
    board = request.app[BOARD_KEY]
    night = await board.show_night(seed)
    return web.json_response({"ok": True, "view": board.scene.view, **dataclasses.asdict(night)})


@routes.post("/api/night/hide")
async def night_hide(request: web.Request) -> web.Response:
    """Go back to the view the night view hid: `{ok, view}`. The body is ignored.

    Outside the night view nothing changes and it still answers ok, because sleep
    mode's wake calls it every time.
    """
    board = request.app[BOARD_KEY]
    await board.hide_night()
    return web.json_response({"ok": True, "view": board.scene.view})


@routes.post("/api/look")
async def look(request: web.Request) -> web.Response:
    """Capture the board through the daemon's look hook: `{clean?: bool}`."""
    clean = parse_look(await read_json_object(request))
    hook = request.app[HOOKS_KEY].look
    if hook is None:
        return web.json_response({"ok": False, "error": _NO_CAMERA}, status=503)
    board = request.app[BOARD_KEY]
    items = [item_to_dict(item) for item in board.scene.items]
    result = await hook(clean)
    # The view tells the caller whether the items are on show or hidden by the TODO view.
    body = {"ok": True, "items": items, "stage": board.stage(), "view": board.scene.view}
    return web.json_response({**body, **result})


@routes.post("/api/calibrate")
async def calibrate(request: web.Request) -> web.Response:
    """Run camera calibration through the daemon's calibrate hook."""
    hook = request.app[HOOKS_KEY].calibrate
    if hook is None:
        return web.json_response({"ok": False, "error": _NO_CAMERA}, status=503)
    return web.json_response(await hook())


@routes.get("/api/status")
async def status(request: web.Request) -> web.Response:
    """Mode, item count, connected pages and stage size, plus whatever the status hook adds."""
    extra_hook = request.app[HOOKS_KEY].status
    extra = await extra_hook() if extra_hook else {}
    return web.json_response({"ok": True, **request.app[BOARD_KEY].status(), **extra})
