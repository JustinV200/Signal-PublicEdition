"""`whiteboard tasks show`: draw the task grid from the console's task list, like board_tasks_show.

It clears the board and redraws every item (whiteboard.tasks_grid), starting the
daemon if it isn't running.
"""

import argparse
from datetime import datetime

from whiteboard.cli.command import EXIT_OK, Command, daemon_connection
from whiteboard.config import CONSOLE_TASKS_FILE, USAGE_FILE, Settings


def add_tasks_arguments(parser: argparse.ArgumentParser) -> None:
    """ACTION (only `show` for now)."""
    parser.add_argument("action", choices=("show",), help="draw the task grid on the board")


def run_tasks(args: argparse.Namespace, settings: Settings) -> int:
    """Draw the grid and print the summary line."""
    # Imported here: the grid pulls in display (numpy), and other commands start quick.
    from whiteboard.tasks_grid import draw_task_grid

    now = datetime.now().astimezone()
    connection = daemon_connection(args, settings)
    print(connection.call(lambda api: draw_task_grid(api, CONSOLE_TASKS_FILE, USAGE_FILE, now)))
    return EXIT_OK


TASKS = Command(
    "tasks", "draw the task grid from the console's task list", add_tasks_arguments, run_tasks
)
