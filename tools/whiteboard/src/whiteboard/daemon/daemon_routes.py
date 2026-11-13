"""Routes the daemon adds to display's app: raw look, fit auto/show, drift check, re-align,
and shutdown.

display owns the scene API (including POST /api/fit {quad} to set or clear
the fit). These are the camera-backed extras, plus /api/shutdown so a daemon
started detached by the MCP server can be stopped cleanly (`whiteboard stop`).
All are under /api/, so they need the token like the rest.
"""

import asyncio
import json

from aiohttp import web

from whiteboard.daemon.camera_hooks import CameraHooks
from whiteboard.daemon.realign import Realigner

CAMERA_HOOKS_KEY = web.AppKey("camera_hooks", CameraHooks)
REALIGNER_KEY = web.AppKey("realigner", Realigner)
STOP_KEY = web.AppKey("stop", asyncio.Event)

NO_CAMERA = "the camera isn't available in this daemon"


def add_daemon_routes(
    app: web.Application,
    hooks: CameraHooks | None,
    realigner: Realigner | None,
    stop: asyncio.Event,
) -> None:
    """Register the daemon's routes on display's app (before it starts).

    Args:
        app: The app from display.create_app.
        hooks: Camera hooks, or None when the camera didn't open (routes then answer 503).
        realigner: Re-aligns on request, or None without a camera (503 too).
        stop: Set by /api/shutdown to end `whiteboard serve`.
    """
    if hooks is not None:
        app[CAMERA_HOOKS_KEY] = hooks
    if realigner is not None:
        app[REALIGNER_KEY] = realigner
    app[STOP_KEY] = stop
    app.router.add_post("/api/look/raw", look_raw)
    app.router.add_post("/api/fit/auto", fit_auto)
    app.router.add_post("/api/fit/show", fit_show)
    app.router.add_post("/api/align/check", align_check)
    app.router.add_post("/api/align/realign", align_realign)
    app.router.add_post("/api/shutdown", shutdown)


async def look_raw(request: web.Request) -> web.Response:
    """`{clean?: bool}`: photograph the whole projector area, ignoring the board fit."""
    hooks = request.app.get(CAMERA_HOOKS_KEY)
    if hooks is None:
        return _no_camera()
    clean = await _read_clean(request)
    if clean is None:
        return web.json_response({"ok": False, "error": "clean must be true or false"}, status=400)
    return web.json_response({"ok": True, **await hooks.look_raw(clean)})


async def fit_auto(request: web.Request) -> web.Response:
    """Re-detect the board outline with the camera and set it as the fit."""
    hooks = request.app.get(CAMERA_HOOKS_KEY)
    return web.json_response(await hooks.fit_auto()) if hooks else _no_camera()


async def fit_show(request: web.Request) -> web.Response:
    """Project the board outline for a few seconds."""
    hooks = request.app.get(CAMERA_HOOKS_KEY)
    return web.json_response(await hooks.fit_show()) if hooks else _no_camera()


async def align_check(request: web.Request) -> web.Response:
    """Measure how far the board has drifted from the current fit. Never re-aligns."""
    hooks = request.app.get(CAMERA_HOOKS_KEY)
    return web.json_response(await hooks.align_check()) if hooks else _no_camera()


async def align_realign(request: web.Request) -> web.Response:
    """Flash the markers now and re-align if anything moved; reports before/after numbers."""
    realigner = request.app.get(REALIGNER_KEY)
    return web.json_response((await realigner.realign()).to_dict()) if realigner else _no_camera()


async def shutdown(request: web.Request) -> web.Response:
    """Ask `whiteboard serve` to stop; it closes the kiosk and camera on the way out."""
    request.app[STOP_KEY].set()
    return web.json_response({"ok": True})


async def _read_clean(request: web.Request) -> bool | None:
    """Read `clean` from an optional JSON body (default True); None if it isn't a bool."""
    text = await request.text()
    try:
        body = json.loads(text) if text.strip() else {}
    except ValueError:
        return None
    clean = body.get("clean", True) if isinstance(body, dict) else None
    return clean if isinstance(clean, bool) else None


def _no_camera() -> web.Response:
    """503 in the API's {ok, error} shape."""
    return web.json_response({"ok": False, "error": NO_CAMERA}, status=503)
