"""Read and validate a save's meta.json.

meta.json is a file on disk anyone could edit, and its board_size divides every
item position on load, so it is checked like any other untrusted input.
"""

import json
from pathlib import Path
from typing import Any

from whiteboard.display.scene import require_number, require_object, require_str
from whiteboard.saves.errors import SaveError

META_FILE = "meta.json"
# What can redraw a live board from its source (the console's Update button): the task
# grid from the console's tasks.json, or the to-do list from the week plans. A fixed
# enum, never a command, because meta.json is a file anyone could edit.
REFRESHERS: tuple[str, ...] = ("tasks", "todo")
# Sane bounds for a board side in board pixels. A tampered tiny size would scale
# items towards infinity on load; a real board is a few hundred to a few thousand px.
MIN_BOARD_PX = 1.0
MAX_BOARD_PX = 100_000.0


def read_meta(folder: Path) -> dict[str, Any]:
    """Read and check meta.json: name, created_at, an in-bounds board_size and the refresher.

    Args:
        folder: The save's folder.

    Returns:
        The meta, with `slug` set to the folder's name.

    Raises:
        SaveError: Missing, not JSON, or a field is wrong (an unknown refresher too).
    """
    try:
        meta = require_object(
            json.loads((folder / META_FILE).read_text(encoding="utf-8")), "meta.json"
        )
        require_str(meta.get("name"), "meta.name")
        require_str(meta.get("created_at"), "meta.created_at")
        board_size = meta.get("board_size")
        if not isinstance(board_size, list) or len(board_size) != 2:
            raise SaveError("meta.board_size must be [width, height]")
        for value in board_size:
            require_number(value, "meta.board_size", minimum=MIN_BOARD_PX, maximum=MAX_BOARD_PX)
        check_refresher(meta.get("refresher"))
    except (OSError, ValueError) as error:
        # ValueError covers bad JSON and SceneError from the field checks.
        raise SaveError(f"unreadable {META_FILE} in {folder.name}: {error}") from error
    return {**meta, "slug": folder.name}


def check_refresher(value: object) -> str | None:
    """`value` if it's None or one of REFRESHERS.

    Raises:
        SaveError: Anything else.
    """
    if value is None:
        return None
    if value not in REFRESHERS:
        raise SaveError(f"refresher must be one of {', '.join(REFRESHERS)}, got {value!r}")
    return str(value)
