"""Saved-board routes: save, list, load and delete whole whiteboards under /api/saves.

Saving copies the projected items and, when the camera is calibrated, takes one
clean capture under the rig's capture lock, keeping the photo and the owner's
extracted ink (see whiteboard.saves). Loading puts the items back, scaled to
the current board, with the ink as an image item covering the board. All
routes are under /api/, so the request guard requires the token like the rest.
"""

import asyncio
from dataclasses import dataclass

import numpy as np
from aiohttp import web

from whiteboard.camera import CameraError, CaptureRig, grab_clean_frame
from whiteboard.display.scene import LOADING_KIND, NightViewError
from whiteboard.display.server import BoardController, read_json_object
from whiteboard.saves import (
    INK_FILE,
    PHOTO_FILE,
    SaveStore,
    drop_missing_images,
    encode_png,
    extract_ink,
    parse_load_request,
    parse_name,
    parse_save_request,
    restored_items,
    slugify,
)

NO_CAMERA_NOTE = "The camera isn't available, so only the projected items were saved."
NO_CALIBRATION_NOTE = (
    "Not calibrated, so only the projected items were saved (no photo or ink). "
    "Run board_calibrate (whiteboard calibrate) to save the owner's drawing too."
)
UNRECTIFIED_NOTE = (
    "The camera frame doesn't match the calibration (recalibrate), so only the projected "
    "items were saved."
)
NIGHT_NOTE = (
    "The night view is showing (sleep mode), so the board wasn't blanked for a photo; only "
    "the projected items were saved."
)


@dataclass(frozen=True)
class SaveContext:
    """What the save routes act on: the live board, the saves folder and the capture rig."""

    board: BoardController
    store: SaveStore
    rig: CaptureRig | None


SAVES_KEY = web.AppKey("saves", SaveContext)


def add_save_routes(app: web.Application, context: SaveContext) -> None:
    """Register GET/POST /api/saves, POST /api/saves/load and POST /api/saves/delete."""
    app[SAVES_KEY] = context
    app.router.add_get("/api/saves", list_saves)
    app.router.add_post("/api/saves", save_board)
    app.router.add_post("/api/saves/load", load_board)
    app.router.add_post("/api/saves/delete", delete_save)


async def list_saves(request: web.Request) -> web.Response:
    """`{ok, saves: [meta]}`, newest first."""
    store = request.app[SAVES_KEY].store
    return web.json_response({"ok": True, "saves": await asyncio.to_thread(store.list_saves)})


async def save_board(request: web.Request) -> web.Response:
    """`{name, description?, overwrite?}` -> the meta, the folder, and a note if scene-only."""
    context = request.app[SAVES_KEY]
    save_request = parse_save_request(await read_json_object(request))
    # Refuse before blanking the board for a photo that couldn't be kept.
    context.store.require_free(save_request.slug, save_request.overwrite)
    stage = context.board.stage()
    # The thinking placeholder is not part of the board; never keep it.
    items = tuple(item for item in context.board.scene.items if item.kind != LOADING_KIND)
    images, note = await _capture_images(context.rig)
    meta = await asyncio.to_thread(
        context.store.save, save_request, items, (stage["width"], stage["height"]), images
    )
    folder = context.store.root / save_request.slug
    return web.json_response({"ok": True, **meta, "folder": str(folder), "note": note})


async def load_board(request: web.Request) -> web.Response:
    """`{name, mode?, include_ink?}` -> what was restored, and any image items left out."""
    context = request.app[SAVES_KEY]
    load_request = parse_load_request(await read_json_object(request))
    saved = await asyncio.to_thread(context.store.load, load_request.slug)
    stage = context.board.stage()
    current_size = (stage["width"], stage["height"])
    items, dropped = drop_missing_images(
        restored_items(saved, current_size, load_request.include_ink)
    )
    await context.board.put_items(items, replace=load_request.replace)
    return web.json_response(
        {
            "ok": True,
            "name": saved.meta["name"],
            "slug": saved.meta["slug"],
            "mode": "replace" if load_request.replace else "overlay",
            "item_count": len(items),
            "ink_projected": load_request.include_ink and saved.ink_content is not None,
            "scaled": list(saved.board_size) != list(current_size),
            "dropped_missing_images": dropped,
        }
    )


async def delete_save(request: web.Request) -> web.Response:
    """`{name}` -> `{ok, deleted: meta}`; 404 if there's no such save."""
    slug = slugify(parse_name(await read_json_object(request)))
    meta = await asyncio.to_thread(request.app[SAVES_KEY].store.delete, slug)
    return web.json_response({"ok": True, "deleted": meta})


async def _capture_images(rig: CaptureRig | None) -> tuple[dict[str, bytes], str | None]:
    """photo.png and ink.png from one clean capture, or ({}, why not) for a scene-only save."""
    if rig is None:
        return {}, NO_CAMERA_NOTE
    if rig.calibration is None:
        return {}, NO_CALIBRATION_NOTE
    try:
        # grab_clean_frame holds the rig's capture lock from blank to restore.
        clean = await grab_clean_frame(rig)
    except CameraError as error:
        return {}, f"Camera problem ({error}), so only the projected items were saved."
    except NightViewError:
        # The board refused the blank before showing it: nothing flashed.
        return {}, NIGHT_NOTE
    if not clean.is_rectified:
        return {}, UNRECTIFIED_NOTE
    return await asyncio.to_thread(_encode_images, clean.image), None


def _encode_images(photo_bgr: np.ndarray) -> dict[str, bytes]:
    """The photo and its extracted ink as PNG bytes, keyed by file name."""
    return {PHOTO_FILE: encode_png(photo_bgr), INK_FILE: encode_png(extract_ink(photo_bgr))}
