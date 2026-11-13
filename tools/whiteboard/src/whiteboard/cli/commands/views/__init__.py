"""The `whiteboard` subcommands that switch or redraw what the board shows: the TODO view,
the idle view, the task grid, the night view, and the keynotes both views show.
Registered in cli/commands/__init__.py.
"""

from whiteboard.cli.commands.views.idle import IDLE
from whiteboard.cli.commands.views.keynotes import KEYNOTES
from whiteboard.cli.commands.views.night import NIGHT
from whiteboard.cli.commands.views.tasks import TASKS
from whiteboard.cli.commands.views.todo import TODO

__all__ = ["IDLE", "KEYNOTES", "NIGHT", "TASKS", "TODO"]
