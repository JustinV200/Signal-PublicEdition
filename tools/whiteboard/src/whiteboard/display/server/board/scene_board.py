"""SceneBoard: the live scene, saved to scene.json and pushed to every board page.

Every change (items, the board fit, the view) is applied with a pure scene op,
saved, then broadcast over the hub. The view is part of the scene, so it survives
restarts: the items, the TODO view, or sleep mode's night view on top of either,
under which switching views and drawing only change the view it goes back to.
BoardController (controller.py) builds on this with the display mode and flashes.
"""

import math
import time
from collections.abc import Sequence
from typing import Any

from whiteboard.display.scene import (
    Item,
    NightView,
    Quad,
    Scene,
    SceneStore,
    clear_items,
    find_item,
    hide_night,
    patch_item,
    remove_item,
    resolve_image_path,
    scene_to_dict,
    set_board_quad,
    show_drawn_items,
    show_night,
    stage_geometry,
    switch_view,
    upsert_item,
)
from whiteboard.display.server.hub import BroadcastHub

DEFAULT_PROJECTOR_SIZE = (1280, 720)
DEFAULT_FIT_HEIGHT = 720


class SceneBoard:
    """Owns the scene and the broadcast hub; see the module docstring."""

    def __init__(
        self,
        store: SceneStore,
        projector_size: tuple[int, int] = DEFAULT_PROJECTOR_SIZE,
        fit_height: int = DEFAULT_FIT_HEIGHT,
    ) -> None:
        """Load the saved scene.

        Args:
            store: Where the scene is persisted.
            projector_size: Projector (width, height) in pixels, from the display bounds.
            fit_height: Logical stage height once a board fit is set.

        Raises:
            OSError: If the scene file exists but can't be read.
        """
        self.hub = BroadcastHub()
        self.projector_size = projector_size
        self._store = store
        self._fit_height = fit_height
        self._scene = store.load()
        # Monotonic time the pages last changed (or a highlight ends); see page_changed_s.
        self._changed_s = -math.inf

    @property
    def scene(self) -> Scene:
        """The current scene (immutable)."""
        return self._scene

    def stage(self) -> dict[str, Any]:
        """The stage geometry: logical size, and the board-fit warp if one is set."""
        return stage_geometry(self._scene.board_quad, self.projector_size, self._fit_height)

    def scene_message(self) -> dict[str, Any]:
        """The WebSocket message that tells a page what to draw."""
        return {"type": "scene", **scene_to_dict(self._scene), "stage": self.stage()}

    async def put_item(self, item: Item) -> Item:
        """Add an item, or replace the one with the same id. Returns the stored item.

        Drawing switches the page back to the items view (scene.show_drawn_items).

        Raises:
            SceneError: If it's an image item whose file doesn't exist.
        """
        _require_image_file(item)
        await self._commit(show_drawn_items(upsert_item(self._scene, item), [item]))
        return item

    async def put_items(self, items: Sequence[Item], replace: bool = False) -> None:
        """Add several items as one change (one save, one broadcast), e.g. a loaded board.

        Args:
            items: Validated items, drawn in this order; same ids replace in place.
            replace: Remove every current item first (the board fit stays).

        Raises:
            SceneError: If an image item's file doesn't exist (nothing is changed).
        """
        for item in items:
            _require_image_file(item)
        scene = clear_items(self._scene) if replace else self._scene
        for item in items:
            scene = upsert_item(scene, item)
        await self._commit(show_drawn_items(scene, items))

    async def patch_item(self, item_id: str, changes: dict[str, Any]) -> Item:
        """Patch one item (see scene.patch_item). Returns the updated item.

        Raises:
            ItemNotFoundError: If no item has that id.
            SceneError: If the patch is invalid, or names a missing image file.
        """
        patched_scene = patch_item(self._scene, item_id, changes)
        item = find_item(patched_scene, item_id)
        _require_image_file(item)
        await self._commit(show_drawn_items(patched_scene, [item]))
        return item

    async def remove_item(self, item_id: str) -> None:
        """Remove one item.

        Raises:
            ItemNotFoundError: If no item has that id.
        """
        await self._commit(remove_item(self._scene, item_id))

    async def clear(self) -> None:
        """Remove every item (the board fit stays)."""
        await self._commit(clear_items(self._scene))

    async def set_fit(self, quad: Quad | None) -> None:
        """Set the board fit quad (from scene.parse_quad), or clear it with None."""
        await self._commit(set_board_quad(self._scene, quad))

    async def set_view(self, view: str) -> None:
        """Show the items ("items"), the TODO view ("todo") or the idle view ("idle"). The
        items are kept either way. Under the night view, it's the view shown when the night
        ends (scene.switch_view).

        Raises:
            SceneError: If `view` isn't one of DAY_VIEWS.
        """
        await self._commit(switch_view(self._scene, view))

    async def show_night(self, seed: int, sky: bool) -> NightView:
        """Show the night view (scene.show_night) and return its settings, with the view it
        goes back to. The items and TODO view wait under it."""
        scene = show_night(self._scene, seed, sky)
        await self._commit(scene)
        return scene.night

    async def hide_night(self) -> None:
        """Go back to the view the night view hid. Outside it, nothing is saved or sent."""
        if self._scene.night is not None:
            await self._commit(hide_night(self._scene))

    async def _commit(self, scene: Scene) -> None:
        # Save first: if the disk write fails, the live scene and the pages stay unchanged.
        self._store.save(scene)
        self._scene = scene
        await self._broadcast(self.scene_message())

    async def _broadcast(self, message: dict[str, Any], lasts_s: float = 0.0) -> None:
        """Push a message to every page, noting when the page stops changing from it."""
        self._changed_s = max(self._changed_s, time.monotonic() + lasts_s)
        await self.hub.broadcast(message)


def _require_image_file(item: Item) -> None:
    # Only new and patched items need an existing file. A saved scene whose
    # snapshot was since pruned still loads; that image just renders nothing.
    if item.kind == "image":
        resolve_image_path(item.content)
