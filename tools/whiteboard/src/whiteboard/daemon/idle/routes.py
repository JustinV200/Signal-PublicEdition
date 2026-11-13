"""The idle view's routes under /api/idle. They sit behind the daemon's request guard
like every /api/* route: loopback only, the X-Signal-Token header, no foreign Origin.

- POST /api/idle/show: switch to the idle view (under the night view, the view it
  goes back to).
- POST /api/idle/hide: switch back to the projected items. On an empty board the
  default rule brings the idle view back after [idle] empty_s.
- POST /api/idle/sync: re-read every source now (files, weather, news) and push.

Each returns IdleController.summary(): `{ok, view, tasks, priorities, agents_active,
upcoming, weather, place, headline}` (counts and flags, no plan or feed text).
"""

from aiohttp import web

from whiteboard.daemon.idle.controller import IdleController

IDLE_KEY = web.AppKey("idle", IdleController)


def add_idle_routes(app: web.Application, controller: IdleController) -> None:
    """Register the /api/idle routes on the daemon's app (before it starts)."""
    app[IDLE_KEY] = controller
    app.router.add_post("/api/idle/show", show)
    app.router.add_post("/api/idle/hide", hide)
    app.router.add_post("/api/idle/sync", sync)


async def show(request: web.Request) -> web.Response:
    """Show the idle view."""
    return web.json_response(await request.app[IDLE_KEY].show())


async def hide(request: web.Request) -> web.Response:
    """Show the projected items again."""
    return web.json_response(await request.app[IDLE_KEY].hide())


async def sync(request: web.Request) -> web.Response:
    """Refresh every source now."""
    return web.json_response(await request.app[IDLE_KEY].sync())
