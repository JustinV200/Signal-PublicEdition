"""Turn a saved board back into scene items for the board as it is now.

Pure apart from the image-file check: items are scaled from the board size they
were saved at to the current one, and the owner's extracted ink (ink.png)
becomes one image item covering the whole board, drawn underneath the rest.
Scaled items go back through the scene parser, so a box that overflows to
infinity is refused instead of reaching scene.json and the page.
"""

from collections.abc import Sequence

from whiteboard.display.scene import (
    Item,
    SceneError,
    item_from_dict,
    item_to_dict,
    resolve_image_path,
)
from whiteboard.saves.errors import SaveError
from whiteboard.saves.store import SavedBoard

INK_ITEM_PREFIX = "saved-ink-"


def restored_items(
    saved: SavedBoard, current_size: tuple[float, float], include_ink: bool
) -> tuple[Item, ...]:
    """The items to put back on the board for one saved board.

    Args:
        saved: The save, from SaveStore.load.
        current_size: The board's (width, height) in board pixels now.
        include_ink: Add the owner's saved strokes (if the save has them).

    Returns:
        The ink item first (so it sits underneath), then the saved items, scaled.

    Raises:
        SaveError: A scaled box isn't a finite, positive size.
    """
    items = scale_items(saved.items, saved.board_size, current_size)
    if not include_ink or saved.ink_content is None:
        return items
    ink_id = INK_ITEM_PREFIX + saved.meta["slug"]
    # A board saved after loading itself still holds its old ink item (now a copy in
    # images/). A fresh id keeps the current ink from replacing it on the board.
    items = tuple(_rebuild(item, {"id": ""}) if item.id == ink_id else item for item in items)
    ink = item_from_dict(
        {
            "id": ink_id,
            "kind": "image",
            "content": saved.ink_content,
            "x": 0,
            "y": 0,
            "w": current_size[0],
            "h": current_size[1],
        }
    )
    return (ink, *items)


def scale_items(
    items: Sequence[Item], saved_size: tuple[float, float], current_size: tuple[float, float]
) -> tuple[Item, ...]:
    """Scale item boxes proportionally from the saved board size to the current one.

    Only the boxes change; content and styles (font sizes too) stay as saved.

    Raises:
        SaveError: A scaled box isn't a finite, positive size (e.g. it overflowed).
    """
    scale_x = current_size[0] / saved_size[0]
    scale_y = current_size[1] / saved_size[1]
    return tuple(
        _rebuild(
            item,
            {
                "x": item.x * scale_x,
                "y": item.y * scale_y,
                "w": item.w * scale_x,
                "h": item.h * scale_y,
            },
        )
        for item in items
    )


def _rebuild(item: Item, changes: dict[str, object]) -> Item:
    """The item with `changes`, validated again by the scene parser.

    Raises:
        SaveError: The changed item is invalid.
    """
    try:
        return item_from_dict({**item_to_dict(item), **changes})
    except SceneError as error:
        raise SaveError(f"saved item {item.id!r} can't be restored: {error}") from error


def drop_missing_images(items: Sequence[Item]) -> tuple[tuple[Item, ...], list[str]]:
    """Leave out image items whose file is gone (e.g. a pruned snapshot or a deleted save).

    BoardController refuses an image item without its file, which would fail the
    whole load over one stale picture.

    Returns:
        (the items to keep, the ids that were left out).
    """
    kept: list[Item] = []
    dropped: list[str] = []
    for item in items:
        if item.kind == "image" and not _image_exists(item.content):
            dropped.append(item.id)
        else:
            kept.append(item)
    return tuple(kept), dropped


def _image_exists(path: str) -> bool:
    """Whether an image item's path passes the board's own check, file included."""
    try:
        resolve_image_path(path)
    except SceneError:
        return False
    return True
