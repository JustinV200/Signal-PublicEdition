"""The AGENTS region and the usage line, from the console's task list and tools/usage.

Same files and readers as the task grid (signal_tasks). Active tasks are ordered with
the ones waiting on the owner first, then by % done (highest first), the task grid's
order; queued and done tasks are only counted.
"""

from typing import Any

from signal_tasks import TaskGroups, UsageSummary

NEEDS_YOU = "needs_you"


def agents_region(groups: TaskGroups) -> dict[str, Any]:
    """`{active: [{name, pct, status, you}], queued, done}` for the page.

    Args:
        groups: signal_tasks.group_tasks of the console's tasks (active by pct already).
    """
    # sorted() is stable, so the pct order holds within each half.
    active = sorted(groups.active, key=lambda task: task.status != NEEDS_YOU)
    return {
        "active": [
            {"name": task.name, "pct": task.pct, "status": task.status, "you": task.you}
            for task in active
        ],
        "queued": len(groups.queued),
        "done": len(groups.done),
    }


def usage_line(usage: UsageSummary) -> dict[str, Any] | None:
    """`{five_hour, week, agents}` (whole percents, None when unknown), or None with no data.

    Args:
        usage: signal_tasks.read_usage's summary (NO_USAGE when there's no file).
    """
    if usage.updated_at is None:
        return None
    return {
        "five_hour": round(usage.five_hour.used_pct) if usage.five_hour else None,
        "week": round(usage.seven_day.used_pct) if usage.seven_day else None,
        "agents": usage.agents,
    }
