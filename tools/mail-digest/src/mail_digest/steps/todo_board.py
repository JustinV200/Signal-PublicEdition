"""Refreshes the whiteboard's TODO view after a successful run.

The view lists todos from life/, which the run may have just changed.
`whiteboard todo sync --if-running` (tools/whiteboard/src/whiteboard/cli/commands/
todo.py) refreshes a running whiteboard daemon and does nothing otherwise, so a
07:00 run never turns the projector on. Best effort: a failure is only logged.
"""

from mail_digest.child_env import run_hidden
from mail_digest.settings import BOARD_SYNC_TIMEOUT_S, WHITEBOARD_PROJECT


def refresh_todo_board() -> None:
    """Run the sync once, hidden. Never raises; run_hidden logs any failure."""
    argv = [
        "uv", "run", "--frozen", "--no-sync", "--project", str(WHITEBOARD_PROJECT),
        "whiteboard", "todo", "sync", "--if-running",
    ]  # fmt: skip
    run_hidden("whiteboard todo sync", argv, BOARD_SYNC_TIMEOUT_S)
