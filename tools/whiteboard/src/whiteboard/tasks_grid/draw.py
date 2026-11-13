"""draw_task_grid: redraw the whole task grid from tasks.json and usage.json in one go.

Shared by the board_tasks_show MCP tool and `whiteboard tasks show`. It
clears the board and draws every item fresh. No save is loaded, so there's
no stale snapshot or ghost ink (the agent-task-grid save's ink is junk). If
the to-do view is up it's hidden first, so the grid shows. Blocking: call it
through DaemonConnection.call (the MCP tool runs that in a worker thread).
"""

from datetime import datetime
from pathlib import Path

from signal_tasks import NO_USAGE, group_tasks, read_tasks, read_usage

from whiteboard.daemon_client import DaemonApi
from whiteboard.display.scene import NIGHT_VIEW, TODO_VIEW
from whiteboard.tasks_grid.items import grid_items, scale_items
from whiteboard.tasks_grid.layout import DESIGN_HEIGHT, DESIGN_WIDTH


def draw_task_grid(api: DaemonApi, tasks_path: Path, usage_path: Path, now: datetime) -> str:
    """Clear the board and draw the grid; returns one line saying what was drawn.

    Args:
        api: The daemon.
        tasks_path: The console's tasks.json.
        usage_path: tools/usage's usage.json.
        now: The current time (aware), for the usage line.

    Raises:
        DaemonApiError: The daemon refused a request (some items may be drawn).
        StateFileError: tasks.json exists but can't be read.
    """
    groups = group_tasks(read_tasks(tasks_path).tasks)
    # Unreadable mid-replace is rare and a redraw is cheap: show "--" rather than wait.
    usage = read_usage(usage_path, now) or NO_USAGE
    status = api.status()
    stage = status.get("stage") or {}
    width = float(stage.get("width") or DESIGN_WIDTH)
    height = float(stage.get("height") or DESIGN_HEIGHT)
    items = scale_items(grid_items(groups, usage, now), width, height)
    if status.get("view") == TODO_VIEW:
        api.todo("hide")
    api.clear()
    for item in items:
        api.put_item(item)
    is_night = status.get("view") == NIGHT_VIEW
    night = " The night view is showing, so the grid waits under it." if is_night else ""
    return (
        f"Drew the task grid: {len(groups.active)} active, {len(groups.queued)} queued, "
        f"{len(groups.done)} done, {len(items)} items on a {width:g}x{height:g} board.{night} "
        "Check it with board_look(clean=false)."
    )
