"""Read the whiteboard's saved boards, current view and item count from its daemon (read-only).

Finding the daemon and its token is whiteboard_api.py's job. The console never
starts the daemon: when it's down, there are no saves and no view. The daemon
logs every request, so callers poll this sparingly.
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import aiohttp

from signal_console.paths import WHITEBOARD_STATE_DIR
from signal_console.status.whiteboard_api import find_whiteboard, get_whiteboard_json

# The refreshers a save may name (tools/whiteboard's saves/meta.py); anything else reads as none.
REFRESHERS = frozenset({"tasks", "todo"})

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class BoardStatus:
    """The whiteboard as the console shows it.

    Attributes:
        saves: [{name, updatedAt, description, refresher}], newest first (the daemon's
            order). description is None when the save has none (an empty one counts as
            none); refresher is "tasks", "todo" or None (no `Show live version` button).
        view: The projected view as the daemon names it, passed through as-is ("items",
            "todo", "idle" or "night" today), or None if the daemon is down or reports no view.
        online: True when the daemon answered, so view None then means "no view field".
        item_count: How many items the board holds (the daemon's `item_count`), or None when
            it is down or an older build sends none. 0 means an "items" view is empty, so the
            page loads a save over it without asking.
    """

    saves: list[dict[str, str | None]] = field(default_factory=list)
    view: str | None = None
    online: bool = False
    item_count: int | None = None


async def read_board_status(
    session: aiohttp.ClientSession, state_dir: Path = WHITEBOARD_STATE_DIR
) -> BoardStatus:
    """Ask the whiteboard daemon for its saves and view; empty if it's down or erroring."""
    target = find_whiteboard(state_dir)
    if target is None:
        return BoardStatus()
    try:
        saves = await get_whiteboard_json(session, target, "/api/saves")
        status = await get_whiteboard_json(session, target, "/api/status")
    except (aiohttp.ClientError, TimeoutError, ValueError) as error:
        log.debug("whiteboard daemon not answering: %s", error)
        return BoardStatus()
    view = status.get("view")
    return BoardStatus(
        _save_list(saves.get("saves")),
        view if isinstance(view, str) else None,
        online=True,
        item_count=_item_count(status.get("item_count")),
    )


def _item_count(value: Any) -> int | None:
    # A count is a non-negative int; anything else (a missing field, a bool, junk) is unknown.
    if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
        return value
    return None


def _save_list(metas: Any) -> list[dict[str, str | None]]:
    # Each save's meta has name and created_at (UTC ISO); newer saves may add updated_at.
    if not isinstance(metas, list):
        return []
    saves = []
    for meta in metas:
        if isinstance(meta, dict) and isinstance(meta.get("name"), str):
            updated = meta.get("updated_at") or meta.get("created_at")
            # "" means no description was saved; the UI then says so.
            description = meta.get("description") or None
            refresher = meta.get("refresher")
            saves.append(
                {
                    "name": meta["name"],
                    "updatedAt": updated if isinstance(updated, str) else None,
                    "description": description if isinstance(description, str) else None,
                    "refresher": refresher if refresher in REFRESHERS else None,
                }
            )
    return saves
