"""Public API of whiteboard.display: what the projector shows, and how it gets there.

Other whiteboard packages (camera, cli, mcp_server, agent) import from here only.
Subpackages: scene (model, ops, store, board fit), server (aiohttp app + board
controller), screen (projector finder + Edge kiosk), static (the board page).
"""

from whiteboard.display.scene import (
    ITEM_KINDS,
    Item,
    ItemNotFoundError,
    Quad,
    Scene,
    SceneError,
    SceneStore,
    Style,
    item_from_dict,
    item_to_dict,
    logical_size,
    parse_quad,
    sanitize_svg,
    scene_to_dict,
    stage_homography,
)
from whiteboard.display.screen import (
    EdgeNotFoundError,
    KioskWindow,
    Monitor,
    ProjectorNotFoundError,
    close_kiosk,
    find_projector,
    launch_kiosk,
    list_monitors,
    pick_projector,
)
from whiteboard.display.server import (
    DISPLAY_MODES,
    STATIC_DIR,
    BoardController,
    CalibrateHook,
    Highlight,
    LookHook,
    Marker,
    StatusHook,
    create_app,
)

__all__ = [
    "DISPLAY_MODES",
    "ITEM_KINDS",
    "STATIC_DIR",
    "BoardController",
    "CalibrateHook",
    "EdgeNotFoundError",
    "Highlight",
    "Item",
    "ItemNotFoundError",
    "KioskWindow",
    "LookHook",
    "Marker",
    "Monitor",
    "ProjectorNotFoundError",
    "Quad",
    "Scene",
    "SceneError",
    "SceneStore",
    "StatusHook",
    "Style",
    "close_kiosk",
    "create_app",
    "find_projector",
    "item_from_dict",
    "item_to_dict",
    "launch_kiosk",
    "list_monitors",
    "logical_size",
    "parse_quad",
    "pick_projector",
    "sanitize_svg",
    "scene_to_dict",
    "stage_homography",
]
