"""The TODO view's routes under /api/todo. They sit behind the daemon's request guard
like every /api/* route: loopback only, the X-Signal-Token header, no foreign Origin.

- POST /api/todo/sync: re-read life/ and push the view. Returns `{ok, view, today,
  plans, overdue, upcoming, of_note, not_shown, newly_done, items}`.
- POST /api/todo/show: switch to the TODO view, then sync (same result).
- POST /api/todo/hide: switch back to the projected items, `{ok, view}`.
- POST /api/todo/done `{item}`: tick the item's box in its plan, then sync (the
  result adds `item` and `changed`).
- POST /api/todo/undone `{item}`: untick it, then sync.

`item` is an item id or a unique piece of its text. 404 when nothing (or more than one
item) matches. 409 when the plan changed during the edit (the line is gone or now
there twice, or the file changed before the write) or can't be written; the plans are
read fresh, so an edit since the last sync alone is fine. 503 when life/ can't be read.
"""

from collections.abc import Awaitable, Callable
from typing import Any

from aiohttp import web

from whiteboard.daemon.todo.controller import TodoController
from whiteboard.display.scene import check_keys, require_str
from whiteboard.display.server import read_json_object
from whiteboard.todo import PlanEditError, TodoLookupError

TODO_KEY = web.AppKey("todo", TodoController)
API_SOURCE = "api"


def add_todo_routes(app: web.Application, controller: TodoController) -> None:
    """Register the /api/todo routes on the daemon's app (before it starts)."""
    app[TODO_KEY] = controller
    app.router.add_post("/api/todo/sync", sync)
    app.router.add_post("/api/todo/show", show)
    app.router.add_post("/api/todo/hide", hide)
    app.router.add_post("/api/todo/done", done)
    app.router.add_post("/api/todo/undone", undone)


async def sync(request: web.Request) -> web.Response:
    """Re-read life/ and push the TODO view; the view on show doesn't change."""
    return await _answer(request.app[TODO_KEY].sync)


async def show(request: web.Request) -> web.Response:
    """Show the TODO view (synced first)."""
    return await _answer(request.app[TODO_KEY].show)


async def hide(request: web.Request) -> web.Response:
    """Show the projected items again."""
    return await _answer(request.app[TODO_KEY].hide)


async def done(request: web.Request) -> web.Response:
    """`{item}`: mark an item done in its week plan."""
    item = await _read_item(request)
    return await _answer(lambda: request.app[TODO_KEY].set_done(item, True, API_SOURCE))


async def undone(request: web.Request) -> web.Response:
    """`{item}`: mark an item not done again (e.g. a cross-out that was a mistake)."""
    item = await _read_item(request)
    return await _answer(lambda: request.app[TODO_KEY].set_done(item, False, API_SOURCE))


async def _read_item(request: web.Request) -> str:
    """The `item` string from the body.

    Raises:
        SceneError: The body isn't `{item: string}` (HTTP 400).
    """
    body = await read_json_object(request)
    check_keys(body, ("item",), "todo request")
    return require_str(body.get("item"), "item")


async def _answer(action: Callable[[], Awaitable[dict[str, Any]]]) -> web.Response:
    """Run a controller call and map the todo errors to HTTP statuses."""
    try:
        return web.json_response(await action())
    except TodoLookupError as error:
        return _error(str(error), 404)
    except PlanEditError as error:
        return _error(str(error), 409)
    except (OSError, UnicodeDecodeError) as error:
        return _error(f"can't read the week plans in life/: {error}", 503)


def _error(message: str, status: int) -> web.Response:
    """An error in the API's {ok, error} shape."""
    return web.json_response({"ok": False, "error": message}, status=status)
