"""Public API of whiteboard.daemon.todo: the TODO view inside the running daemon.

TodoController syncs the view from life/ and ticks items, add_todo_routes exposes it
under /api/todo, and StrikeWatcher turns a cross-out on the real board into a tick.
"""

from whiteboard.daemon.todo.controller import TodoController
from whiteboard.daemon.todo.files import TodoFiles
from whiteboard.daemon.todo.routes import add_todo_routes
from whiteboard.daemon.todo.strike_confirm import StrikeConfirm, StrikeVerdict
from whiteboard.daemon.todo.strike_watch import StrikeHooks, StrikeWatcher

__all__ = [
    "StrikeConfirm",
    "StrikeHooks",
    "StrikeVerdict",
    "StrikeWatcher",
    "TodoController",
    "TodoFiles",
    "add_todo_routes",
]
