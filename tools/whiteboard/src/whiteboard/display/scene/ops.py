"""Pure scene operations: each takes a Scene and returns a new one, never mutating the input.

The server's BoardController applies these, persists the result and broadcasts it.
Items keep their drawing order; replacing an item keeps its place in the stack.
The view switches live here too. The night view sits on top of the others: while it
shows, switching views or drawing only changes the view it goes back to, so nothing
lights up the board until it ends.
"""

import dataclasses
from collections.abc import Sequence
from typing import Any

from whiteboard.display.scene.model import (
    DAY_VIEWS,
    ITEMS_VIEW,
    LOADING_KIND,
    NIGHT_VIEW,
    Item,
    ItemNotFoundError,
    NightView,
    Quad,
    Scene,
    SceneError,
)
from whiteboard.display.scene.parse import merge_item


def find_item(scene: Scene, item_id: str) -> Item:
    """Return the item with this id.

    Raises:
        ItemNotFoundError: If no item has that id.
    """
    for item in scene.items:
        if item.id == item_id:
            return item
    raise ItemNotFoundError(f"no item with id {item_id!r}")


def upsert_item(scene: Scene, item: Item) -> Scene:
    """Add an item on top, or replace the item with the same id in place.

    Args:
        scene: The current scene.
        item: A validated item (from parse.item_from_dict).

    Returns:
        The new scene.
    """
    if any(existing.id == item.id for existing in scene.items):
        items = tuple(item if existing.id == item.id else existing for existing in scene.items)
    else:
        items = (*scene.items, item)
    return dataclasses.replace(scene, items=items)


def patch_item(scene: Scene, item_id: str, changes: dict[str, Any]) -> Scene:
    """Move, resize, restyle or re-content one item (see parse.merge_item).

    Raises:
        ItemNotFoundError: If no item has that id.
        SceneError: If the patch is invalid.
    """
    return upsert_item(scene, merge_item(find_item(scene, item_id), changes))


def remove_item(scene: Scene, item_id: str) -> Scene:
    """Remove one item.

    Raises:
        ItemNotFoundError: If no item has that id.
    """
    find_item(scene, item_id)
    return dataclasses.replace(scene, items=tuple(i for i in scene.items if i.id != item_id))


def clear_items(scene: Scene) -> Scene:
    """Remove every item. The board fit is kept: it describes the room, not the drawing."""
    return dataclasses.replace(scene, items=())


def set_board_quad(scene: Scene, quad: Quad | None) -> Scene:
    """Set the board fit (a quad from fit.parse_quad), or clear it with None."""
    return dataclasses.replace(scene, board_quad=quad)


def switch_view(scene: Scene, view: str) -> Scene:
    """Show the items, the TODO view or the idle view. While the night view shows, this only
    changes the view it goes back to.

    Raises:
        SceneError: If `view` isn't one of DAY_VIEWS (the night view has show_night).
    """
    if view not in DAY_VIEWS:
        raise SceneError(f"view must be one of {', '.join(DAY_VIEWS)}, got {view!r}")
    if scene.night is not None:
        night = dataclasses.replace(scene.night, previous_view=view)
        return dataclasses.replace(scene, night=night)
    return dataclasses.replace(scene, view=view)


def show_drawn_items(scene: Scene, items: Sequence[Item]) -> Scene:
    """Switch to the items view when real items were drawn or moved.

    Claude drawing while the TODO or idle view is up would otherwise draw out of sight.
    The "thinking" box doesn't count: a board agent turn starting must not hide the list.
    Under the night view the drawing waits, hidden, and shows when the night ends.
    """
    if any(item.kind != LOADING_KIND for item in items):
        return switch_view(scene, ITEMS_VIEW)
    return scene


def show_night(scene: Scene, seed: int, sky: bool) -> Scene:
    """Switch to the night view with this sky (`seed` from parse.parse_seed).

    Already showing, only the sky changes: the view to go back to stays the one
    from before the night.
    """
    previous_view = scene.night.previous_view if scene.night is not None else scene.view
    return dataclasses.replace(scene, view=NIGHT_VIEW, night=NightView(seed, sky, previous_view))


def hide_night(scene: Scene) -> Scene:
    """Go back to the view the night view hid. Outside the night view, the scene is unchanged."""
    if scene.night is None:
        return scene
    return dataclasses.replace(scene, view=scene.night.previous_view, night=None)
