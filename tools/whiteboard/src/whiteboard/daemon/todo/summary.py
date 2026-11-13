"""What a TODO sync reports back to the CLI and to Claude, and the view's "nothing here" note."""

from collections.abc import Sequence
from datetime import date
from pathlib import Path
from typing import Any

from whiteboard.todo import (
    GROUP_OF_NOTE,
    GROUP_OVERDUE,
    WINDOW_DAYS,
    TodoGroup,
    TodoLayout,
    TrackResult,
    WeekPlan,
    week_folder_name,
)

_COUNTED_GROUPS = (GROUP_OVERDUE, GROUP_OF_NOTE)
# Every day group is counted together under this one name.
_UPCOMING = "upcoming"


def sync_summary(
    layout: TodoLayout,
    groups: Sequence[TodoGroup],
    result: TrackResult,
    sources: tuple[Sequence[WeekPlan], Path],
) -> dict[str, Any]:
    """Counts per section, the plans read, and every shown item with its id.

    `not_shown` counts rows cut for room plus old overdue items folded into the heading.

    Args:
        layout: What the view shows.
        groups: The groups it was laid out from (for the folded overdue items).
        result: The sync's tracking result (done and newly done ids).
        sources: The plan files read, and the repo root their paths are given relative to.
    """
    plans, repo_root = sources
    counts = {GROUP_OVERDUE: 0, _UPCOMING: 0, GROUP_OF_NOTE: 0}
    items = []
    for place in layout.rows:
        entry = place.row.entry
        group = place.group_key if place.group_key in _COUNTED_GROUPS else _UPCOMING
        counts[group] += 1
        items.append(
            {
                "id": entry.id,
                "tag": entry.tag,
                "text": entry.text,
                "due": entry.due.day.isoformat() if entry.due else None,
                "group": group,
                "done": entry.id in result.done_ids,
            }
        )
    return {
        "plans": [relative_path(plan.path, repo_root) for plan in plans],
        **counts,
        "not_shown": layout.hidden_rows + sum(len(group.folded) for group in groups),
        "newly_done": sorted(result.newly_done),
        "items": items,
    }


def empty_note(groups: Sequence[TodoGroup], plans: Sequence[WeekPlan], today: date) -> str:
    """What the view says when it has nothing to list ("" when it has)."""
    if not plans:
        return f"No week plan for {week_folder_name(today)} in life/ yet."
    if not groups:
        return f"Nothing due in the next {WINDOW_DAYS} days."
    return ""


def relative_path(path: Path, root: Path) -> str:
    """`path` relative to `root` in forward slashes, or as given if it's outside."""
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return str(path)
