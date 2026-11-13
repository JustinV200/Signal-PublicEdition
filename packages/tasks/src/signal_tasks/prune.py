"""Which done tasks tasks.json keeps: none older than a day, and at most the newest 20.

Active and queued tasks are never pruned; only the orchestrator removes them.
"""

from datetime import datetime, timedelta

from signal_tasks.model import Task

DONE_KEEP_FOR = timedelta(hours=24)
DONE_KEEP_MAX = 20


def prune(tasks: list[Task], now: datetime) -> list[Task]:
    """`tasks` without the done ones past DONE_KEEP_FOR or beyond the newest DONE_KEEP_MAX.

    Args:
        tasks: The file's tasks, in file order.
        now: The current time (aware).

    Returns:
        The kept tasks, in the same order.
    """
    cutoff = now - DONE_KEEP_FOR
    done = [task for task in tasks if task.status == "done"]
    fresh = [task for task in done if _at(task) is not None and _at(task) >= cutoff]
    fresh.sort(key=lambda task: _at(task), reverse=True)
    kept_done = {task.id for task in fresh[:DONE_KEEP_MAX]}
    return [task for task in tasks if task.status != "done" or task.id in kept_done]


def _at(task: Task) -> datetime | None:
    # A done task with an unreadable time can't be dated, so it's pruned.
    try:
        at = datetime.fromisoformat(task.updated_at)
    except ValueError:
        return None
    return at if at.tzinfo else at.astimezone()
