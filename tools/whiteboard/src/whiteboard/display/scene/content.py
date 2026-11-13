"""Per-kind checks on an item's `content` before it goes into the scene.

- svg: sanitized markup (svg_sanitize.py).
- rough: a JSON list of shapes, validated and stored as compact JSON text.
- image: a repo-relative PNG/JPEG path, checked as a string only (image_paths.py).
  Whether the file exists is checked on create/patch, not when scene.json loads.
- mermaid, text, markdown, math: any string; the page renders them with
  sanitizing libraries (mermaid strict mode, DOMPurify, KaTeX without trust).
"""

import json
from typing import Any

from whiteboard.display.scene.fields import check_keys, require_number, require_object, require_str
from whiteboard.display.scene.image_paths import check_image_path
from whiteboard.display.scene.model import SceneError
from whiteboard.display.scene.svg_sanitize import sanitize_svg

# Rough shapes, in item-local pixels (0,0 = the item's top-left): shape -> required numbers.
ROUGH_SHAPES: dict[str, tuple[str, ...]] = {
    "rect": ("x", "y", "w", "h"),
    "ellipse": ("x", "y", "w", "h"),
    "line": ("x1", "y1", "x2", "y2"),
    "arrow": ("x1", "y1", "x2", "y2"),
    "path": (),
}
# Optional per-shape overrides of the item style.
_ROUGH_OPTIONAL = ("color", "stroke_width")


def normalize_content(kind: str, content: Any) -> str:
    """Validate an item's content for its kind and return the string to store.

    Args:
        kind: One of ITEM_KINDS.
        content: The raw content. Usually a string; a rough item may also pass
            its shape list directly.

    Returns:
        The content as stored: sanitized SVG, compact rough JSON, or the input string.

    Raises:
        SceneError: If the content doesn't fit its kind.
    """
    if kind == "rough":
        return _normalize_rough(content)
    text = require_str(content, "content")
    if kind == "svg":
        return sanitize_svg(text)
    if kind == "image":
        check_image_path(text)
    return text


def _normalize_rough(content: Any) -> str:
    shapes = content
    if isinstance(content, str):
        try:
            shapes = json.loads(content)
        except json.JSONDecodeError as error:
            raise SceneError(f"rough content is not valid JSON: {error}") from error
    if not isinstance(shapes, list):
        raise SceneError("rough content must be a JSON list of shapes")
    for position, shape in enumerate(shapes):
        _check_rough_shape(shape, f"rough shape [{position}]")
    return json.dumps(shapes, separators=(",", ":"))


def _check_rough_shape(shape: Any, label: str) -> None:
    shape = require_object(shape, label)
    kind = shape.get("shape")
    if kind not in ROUGH_SHAPES:
        raise SceneError(f"{label}: shape must be one of {', '.join(ROUGH_SHAPES)}, got {kind!r}")
    required = ROUGH_SHAPES[kind] + (("d",) if kind == "path" else ())
    check_keys(shape, ("shape", *required, *_ROUGH_OPTIONAL), label)
    for key in ROUGH_SHAPES[kind]:
        require_number(shape.get(key), f"{label}.{key}")
    if kind == "path":
        require_str(shape.get("d"), f"{label}.d")
    if "color" in shape:
        require_str(shape["color"], f"{label}.color")
    if "stroke_width" in shape:
        require_number(shape["stroke_width"], f"{label}.stroke_width", minimum=0)
