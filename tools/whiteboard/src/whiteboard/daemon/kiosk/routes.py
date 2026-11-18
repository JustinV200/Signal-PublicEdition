"""POST /api/kiosk/open: reopen the board kiosk now if no board page is connected.

Sleep mode's night guard calls it when the night view isn't on the projector but
the daemon is up. It runs the watchdog's own check, so its backoff applies here
too, and it answers 409 once the watchdog has stopped. Under /api/, so the
request guard needs the token, like /api/night/show.
"""

import asyncio

from aiohttp import web

from whiteboard.daemon.kiosk.watchdog import KioskWatchdog

WATCHDOG_KEY = web.AppKey("kiosk_watchdog", KioskWatchdog)
KIOSK_OFF = "the kiosk is off (no projector, or [display] launch_kiosk = false)"
KIOSK_STOPPED = "the daemon is shutting down"


def add_kiosk_routes(app: web.Application, watchdog: KioskWatchdog | None) -> None:
    """Register POST /api/kiosk/open (before the app starts).

    Args:
        app: The daemon's app.
        watchdog: The kiosk's watchdog, or None when the kiosk is off (the route answers 409).
    """
    if watchdog is not None:
        app[WATCHDOG_KEY] = watchdog
    app.router.add_post("/api/kiosk/open", open_kiosk)


async def open_kiosk(request: web.Request) -> web.Response:
    """`{ok, opened}`: opened is false when a page is connected or a relaunch is backing off."""
    watchdog = request.app.get(WATCHDOG_KEY)
    if watchdog is None:
        return web.json_response({"ok": False, "error": KIOSK_OFF}, status=409)
    if watchdog.is_stopped:
        return web.json_response({"ok": False, "error": KIOSK_STOPPED}, status=409)
    return web.json_response({"ok": True, "opened": await asyncio.to_thread(watchdog.check)})
