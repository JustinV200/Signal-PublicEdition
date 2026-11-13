"""Public API of whiteboard.saves: save whole whiteboards and bring them back later.

A save keeps the projected items, a clean photo of the owner's ink and that ink
extracted as bright strokes on a transparent background, so loading it can
project the owner's old drawing back onto the board. The daemon's /api/saves
routes use this package; it has no camera or server code of its own.
"""

from whiteboard.saves.errors import SaveError, SaveNotFoundError
from whiteboard.saves.ink import encode_png, extract_ink
from whiteboard.saves.meta import REFRESHERS
from whiteboard.saves.requests import (
    LOAD_MODES,
    LoadRequest,
    SaveRequest,
    parse_load_request,
    parse_name,
    parse_save_request,
)
from whiteboard.saves.restore import drop_missing_images, restored_items, scale_items
from whiteboard.saves.slug import slugify
from whiteboard.saves.store import INK_FILE, PHOTO_FILE, SavedBoard, SaveStore

__all__ = [
    "INK_FILE",
    "LOAD_MODES",
    "PHOTO_FILE",
    "REFRESHERS",
    "LoadRequest",
    "SaveError",
    "SaveNotFoundError",
    "SaveRequest",
    "SaveStore",
    "SavedBoard",
    "drop_missing_images",
    "encode_png",
    "extract_ink",
    "parse_load_request",
    "parse_name",
    "parse_save_request",
    "restored_items",
    "scale_items",
    "slugify",
]
