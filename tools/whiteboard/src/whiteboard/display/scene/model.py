"""The scene data model: items Claude projects onto the board, the optional board fit, and
which view the page shows (items, TODO, idle or night).

Everything here is a frozen dataclass so scene ops (ops.py) stay pure: they take a
Scene and return a new one. Coordinates are in stage pixels: projector pixels
(1280x720) with no board fit, or logical board pixels once a fit is set (see fit.py).
"""

import dataclasses
from dataclasses import dataclass, field
from typing import Any

# Every item kind the board page knows how to render.
ITEM_KINDS: tuple[str, ...] = (
    "svg",
    "mermaid",
    "text",
    "markdown",
    "math",
    "rough",
    "image",
    "loading",
)
# The "Claude is thinking" placeholder: a daemon-managed item with this one reserved id.
LOADING_KIND = "loading"
LOADING_ID = "loading"
# What the page shows: the projected items, the TODO view (whiteboard.todo) over a
# black board, the idle view (the default when nothing is drawn, whiteboard.idle), or
# the night view (sleep mode's dim sky, static/night/). The items stay in the scene in
# every view, so switching back is instant.
ITEMS_VIEW = "items"
TODO_VIEW = "todo"
IDLE_VIEW = "idle"
NIGHT_VIEW = "night"
VIEWS: tuple[str, ...] = (ITEMS_VIEW, TODO_VIEW, IDLE_VIEW, NIGHT_VIEW)
# The views the night view can hide, and goes back to when it ends.
DAY_VIEWS: tuple[str, ...] = (ITEMS_VIEW, TODO_VIEW, IDLE_VIEW)

# Bright cyan: shows up well when projected onto a white board in a lit room.
DEFAULT_COLOR = "#00e5ff"
DEFAULT_STROKE_WIDTH = 3.0
# 0 means "auto-fit the text to the item's box".
AUTO_FONT_SIZE = 0.0
DEFAULT_CREATED_BY = "claude"

Point = tuple[float, float]
# Four corners in projector pixels, clockwise from the top-left: TL, TR, BR, BL.
Quad = tuple[Point, Point, Point, Point]


class SceneError(ValueError):
    """Raised for an invalid item, style, quad or scene file."""


class ItemNotFoundError(LookupError):
    """Raised when an op names an item id that isn't in the scene."""


class NightViewError(RuntimeError):
    """Raised when something would light up the board while the night view shows (HTTP 409)."""


@dataclass(frozen=True)
class Style:
    """How an item is drawn. `rough` turns on rough.js's hand-drawn wobble for rough shapes."""

    color: str = DEFAULT_COLOR
    stroke_width: float = DEFAULT_STROKE_WIDTH
    font_size: float = AUTO_FONT_SIZE
    rough: bool = True
    opacity: float = 1.0


@dataclass(frozen=True)
class Item:
    """One thing on the board: a box (x, y, w, h) in stage pixels plus kind-specific content."""

    id: str
    kind: str
    x: float
    y: float
    w: float
    h: float
    content: str
    style: Style = field(default_factory=Style)
    created_by: str = DEFAULT_CREATED_BY
    created_at: str = ""


@dataclass(frozen=True)
class NightView:
    """The night view sleep mode asks for: which sky, and the view it hides.

    Attributes:
        seed: Picks the sky; tools/sleepmode sends YYYYMMDD of the evening the night began.
        previous_view: The view underneath (one of DAY_VIEWS), shown again when it ends.
    """

    seed: int
    previous_view: str


@dataclass(frozen=True)
class Scene:
    """Everything projected: items in drawing order (later ones on top), the board fit,
    which view the page shows (VIEWS), and the night view's settings, set exactly while
    `view` is NIGHT_VIEW."""

    items: tuple[Item, ...] = ()
    board_quad: Quad | None = None
    view: str = ITEMS_VIEW
    night: NightView | None = None


def item_to_dict(item: Item) -> dict[str, Any]:
    """Convert an Item to plain JSON-ready data (the style becomes a nested dict).

    Args:
        item: The item to convert.

    Returns:
        A dict with the same keys as the dataclass fields.
    """
    return dataclasses.asdict(item)


def scene_to_dict(scene: Scene) -> dict[str, Any]:
    """Convert a Scene to the JSON shape stored in scene.json and served by GET /api/scene.

    Args:
        scene: The scene to convert.

    Returns:
        `{"items": [...], "board_quad": [[x, y], ...] | None, "view": one of VIEWS,
        "night": {"seed", "previous_view"} | None}`.
    """
    quad = [list(point) for point in scene.board_quad] if scene.board_quad is not None else None
    items = [item_to_dict(item) for item in scene.items]
    night = dataclasses.asdict(scene.night) if scene.night is not None else None
    return {"items": items, "board_quad": quad, "view": scene.view, "night": night}
