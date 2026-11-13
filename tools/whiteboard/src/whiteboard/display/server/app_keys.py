"""Typed aiohttp app keys, and the optional daemon hooks stored under them.

The display package has no camera. The daemon passes async callables for the
camera-backed endpoints when it builds the app (see app.create_app). When a
hook is missing, its endpoint answers 503.
"""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from aiohttp import web

from whiteboard.display.server.board import BoardController

# look(clean) -> {png_path, width, height, ...}; the route adds the scene items.
LookHook = Callable[[bool], Awaitable[dict[str, Any]]]
# calibrate() -> {ok, error?, reprojection_error_px}
CalibrateHook = Callable[[], Awaitable[dict[str, Any]]]
# status() -> extra fields merged into GET /api/status (camera, calibration, agent...).
StatusHook = Callable[[], Awaitable[dict[str, Any]]]


@dataclass(frozen=True)
class Hooks:
    """The daemon's optional callbacks for camera-backed endpoints."""

    look: LookHook | None = None
    calibrate: CalibrateHook | None = None
    status: StatusHook | None = None


BOARD_KEY = web.AppKey("board", BoardController)
HOOKS_KEY = web.AppKey("hooks", Hooks)
