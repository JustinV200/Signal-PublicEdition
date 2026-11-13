"""Build Items, Styles and Scenes from untrusted JSON (API bodies and scene.json).

This is the scene's trust boundary: every Item in a Scene was built here, so its
fields are typed, its box is finite and positive, and its content passed the
per-kind checks in content.py.
"""

import re
import uuid
from datetime import UTC, datetime
from typing import Any

from whiteboard.display.scene.content import normalize_content
from whiteboard.display.scene.fields import (
    check_keys,
    require_bool,
    require_number,
    require_object,
    require_positive,
    require_str,
)
from whiteboard.display.scene.fit import parse_quad
from whiteboard.display.scene.model import (
    DAY_VIEWS,
    DEFAULT_CREATED_BY,
    ITEM_KINDS,
    ITEMS_VIEW,
    LOADING_ID,
    LOADING_KIND,
    NIGHT_VIEW,
    VIEWS,
    Item,
    NightView,
    Scene,
    SceneError,
    Style,
    item_to_dict,
)

ITEM_KEYS: tuple[str, ...] = (
    "id",
    "kind",
    "x",
    "y",
    "w",
    "h",
    "content",
    "style",
    "created_by",
    "created_at",
)
STYLE_KEYS: tuple[str, ...] = ("color", "stroke_width", "font_size", "rough", "opacity")
# Patches may move, resize, restyle or re-content an item, but not change what it is.
PATCHABLE_KEYS: tuple[str, ...] = ("x", "y", "w", "h", "content", "style")
SCENE_KEYS: tuple[str, ...] = ("items", "board_quad", "view", "night")
NIGHT_KEYS: tuple[str, ...] = ("seed", "sky", "previous_view")
# The night sky's generator (static/night/random.js, mulberry32) takes a 32-bit seed.
MAX_NIGHT_SEED = 2**32 - 1

# Ids are used in DOM ids and URLs, so keep them to a safe alphabet.
_ITEM_ID = re.compile(r"[A-Za-z0-9_.-]{1,64}")
# Hex, a named colour, or rgb()/hsl() with plain numbers: nothing that could carry CSS syntax.
_CSS_COLOR = re.compile(r"#[0-9a-fA-F]{3,8}|[a-zA-Z]{3,20}|(rgb|rgba|hsl|hsla)\([0-9.,%\s]+\)")
_ID_SUFFIX_HEX_CHARS = 8


def item_from_dict(data: Any) -> Item:
    """Validate raw item data and build an Item. Missing id and created_at are generated.

    Args:
        data: A JSON object with ITEM_KEYS (kind, x, y, w, h and content are required).

    Returns:
        The validated Item.

    Raises:
        SceneError: On a missing or unknown key, a bad type or value, or bad content.
    """
    data = require_object(data, "item")
    check_keys(data, ITEM_KEYS, "item")
    kind = data.get("kind")
    if kind not in ITEM_KINDS:
        raise SceneError(f"item.kind must be one of {', '.join(ITEM_KINDS)}, got {kind!r}")
    if "content" not in data:
        raise SceneError("item.content is required")
    item_id = _item_id(data.get("id"), kind)
    # The loading box owns its id: nothing else may take it, and it can't take another.
    if (kind == LOADING_KIND) != (item_id == LOADING_ID):
        raise SceneError(f"the id {LOADING_ID!r} is reserved for items of kind {LOADING_KIND!r}")
    return Item(
        id=item_id,
        kind=kind,
        x=require_number(data.get("x"), "item.x"),
        y=require_number(data.get("y"), "item.y"),
        w=require_positive(data.get("w"), "item.w"),
        h=require_positive(data.get("h"), "item.h"),
        content=normalize_content(kind, data["content"]),
        style=style_from_dict(data.get("style", {})),
        created_by=require_str(data.get("created_by", DEFAULT_CREATED_BY), "item.created_by"),
        created_at=require_str(data.get("created_at") or _now_iso(), "item.created_at"),
    )


def style_from_dict(data: Any) -> Style:
    """Validate raw style data; keys left out keep the Style defaults.

    Raises:
        SceneError: On an unknown key or a bad value.
    """
    data = require_object(data, "style")
    check_keys(data, STYLE_KEYS, "style")
    values: dict[str, Any] = {}
    if "color" in data:
        values["color"] = _css_color(data["color"])
    if "stroke_width" in data:
        values["stroke_width"] = require_number(
            data["stroke_width"], "style.stroke_width", minimum=0
        )
    if "font_size" in data:
        # 0 means auto-fit.
        values["font_size"] = require_number(data["font_size"], "style.font_size", minimum=0)
    if "rough" in data:
        values["rough"] = require_bool(data["rough"], "style.rough")
    if "opacity" in data:
        values["opacity"] = require_number(data["opacity"], "style.opacity", minimum=0, maximum=1)
    return Style(**values)


def merge_item(item: Item, changes: Any) -> Item:
    """Apply a patch to an item and re-validate the result.

    Style changes merge key by key into the current style.

    Args:
        item: The current item.
        changes: A JSON object with any of PATCHABLE_KEYS.

    Returns:
        The patched, validated Item (same id, kind and creation info).

    Raises:
        SceneError: On a key outside PATCHABLE_KEYS or an invalid merged value.
    """
    changes = require_object(changes, "patch")
    check_keys(changes, PATCHABLE_KEYS, "patch")
    merged = item_to_dict(item)
    style_changes = require_object(changes.get("style", {}), "patch.style")
    merged.update({key: value for key, value in changes.items() if key != "style"})
    merged["style"] = {**merged["style"], **style_changes}
    return item_from_dict(merged)


def scene_from_dict(data: Any) -> Scene:
    """Build a Scene from the JSON stored in scene.json.

    Raises:
        SceneError: If the data or any item in it is invalid.
    """
    data = require_object(data, "scene")
    check_keys(data, SCENE_KEYS, "scene")
    raw_items = data.get("items", [])
    if not isinstance(raw_items, list):
        raise SceneError("scene.items must be a list")
    quad = data.get("board_quad")
    # Files written before the TODO view existed have no view: the items.
    view = parse_view(data.get("view", ITEMS_VIEW))
    night = data.get("night")
    if (view == NIGHT_VIEW) != (night is not None):
        raise SceneError("scene.night must be set exactly when the view is night")
    return Scene(
        items=tuple(item_from_dict(raw) for raw in raw_items),
        board_quad=parse_quad(quad) if quad is not None else None,
        view=view,
        night=night_from_dict(night) if night is not None else None,
    )


def night_from_dict(data: Any) -> NightView:
    """Build the night view's settings as stored in scene.json.

    Raises:
        SceneError: On a missing or unknown key, a bad seed, or a previous view that
            isn't one of DAY_VIEWS.
    """
    data = require_object(data, "scene.night")
    check_keys(data, NIGHT_KEYS, "scene.night")
    previous_view = data.get("previous_view")
    if previous_view not in DAY_VIEWS:
        raise SceneError(
            f"scene.night.previous_view must be one of {', '.join(DAY_VIEWS)}, "
            f"got {previous_view!r}"
        )
    sky = require_bool(data.get("sky"), "scene.night.sky")
    return NightView(parse_seed(data.get("seed")), sky, previous_view)


def parse_seed(value: Any) -> int:
    """Check a night sky seed: an integer from 0 to MAX_NIGHT_SEED.

    Raises:
        SceneError: If it isn't one.
    """
    # bool is an int in Python, but `true` isn't a seed.
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= MAX_NIGHT_SEED:
        raise SceneError(f"seed must be an integer from 0 to {MAX_NIGHT_SEED}, got {value!r}")
    return value


def parse_view(value: Any) -> str:
    """Check a view name (one of VIEWS).

    Raises:
        SceneError: If it isn't one.
    """
    if value not in VIEWS:
        raise SceneError(f"view must be one of {', '.join(VIEWS)}, got {value!r}")
    return value


def _item_id(raw_id: Any, kind: str) -> str:
    if raw_id is None or raw_id == "":
        if kind == LOADING_KIND:
            return LOADING_ID
        return f"{kind}-{uuid.uuid4().hex[:_ID_SUFFIX_HEX_CHARS]}"
    item_id = require_str(raw_id, "item.id")
    if not _ITEM_ID.fullmatch(item_id):
        raise SceneError(f"item.id must be 1-64 of A-Z a-z 0-9 _ . -, got {item_id!r}")
    return item_id


def _css_color(value: Any) -> str:
    color = require_str(value, "style.color").strip()
    if not _CSS_COLOR.fullmatch(color):
        raise SceneError(f"style.color must be a CSS colour like #00e5ff, got {value!r}")
    return color


def _now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")
