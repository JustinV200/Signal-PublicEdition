"""Parse and validate JSON request bodies for the /api routes.

Each parser takes the decoded body and returns typed values, raising SceneError
(mapped to HTTP 400 by the error middleware) on anything malformed.
"""

import json
from datetime import datetime, timedelta
from typing import Any

from aiohttp import web

from whiteboard.display.scene import (
    Quad,
    SceneError,
    check_keys,
    parse_quad,
    parse_seed,
    require_bool,
    require_number,
    require_object,
    require_positive,
    require_str,
)
from whiteboard.display.server.board import Highlight, Marker

DEFAULT_HIGHLIGHT_SECONDS = 3.0
# A highlight that outlives this is almost certainly a mistake.
MAX_HIGHLIGHT_SECONDS = 60.0
# Marker images may only come from the page's own origin or an inline data: URL,
# so the board page never fetches anything from the network.
_MARKER_URL_PREFIXES = ("data:image/", "/")
# A night runs noon to noon, so 01:00 belongs to the night that began the evening before.
_NIGHT_DAY_OFFSET = timedelta(hours=12)


async def read_json_object(request: web.Request) -> dict[str, Any]:
    """Decode the request body as a JSON object. An empty body counts as `{}`.

    Raises:
        SceneError: If the body isn't valid JSON or isn't an object.
    """
    text = await request.text()
    if not text.strip():
        return {}
    try:
        return require_object(json.loads(text), "request body")
    except json.JSONDecodeError as error:
        raise SceneError(f"request body is not valid JSON: {error}") from error


def parse_highlight(body: dict[str, Any]) -> Highlight:
    """Parse `{x, y, w, h, seconds?}` for POST /api/highlight."""
    check_keys(body, ("x", "y", "w", "h", "seconds"), "highlight")
    seconds = body.get("seconds", DEFAULT_HIGHLIGHT_SECONDS)
    return Highlight(
        x=require_number(body.get("x"), "x"),
        y=require_number(body.get("y"), "y"),
        w=require_positive(body.get("w"), "w"),
        h=require_positive(body.get("h"), "h"),
        seconds=min(require_positive(seconds, "seconds"), MAX_HIGHLIGHT_SECONDS),
    )


def parse_mode(body: dict[str, Any]) -> tuple[str, tuple[Marker, ...]]:
    """Parse `{mode, markers?: [{url, x, y, w, h}]}` for POST /api/mode.

    The mode name itself is checked by BoardController.set_mode.
    """
    check_keys(body, ("mode", "markers"), "mode request")
    mode = require_str(body.get("mode"), "mode")
    raw_markers = body.get("markers", [])
    if not isinstance(raw_markers, list):
        raise SceneError("markers must be a list")
    return mode, tuple(
        _parse_marker(raw, f"markers[{index}]") for index, raw in enumerate(raw_markers)
    )


def parse_fit(body: dict[str, Any]) -> Quad | None:
    """Parse `{quad: [[x, y] x4] | null}` for POST /api/fit. null clears the fit."""
    check_keys(body, ("quad",), "fit request")
    if "quad" not in body:
        raise SceneError("fit request needs a quad (or null to clear the fit)")
    return None if body["quad"] is None else parse_quad(body["quad"])


def parse_look(body: dict[str, Any]) -> bool:
    """Parse `{clean?: bool}` for POST /api/look. Returns whether to blank the page first."""
    check_keys(body, ("clean",), "look request")
    return require_bool(body.get("clean", True), "clean")


def parse_night(body: dict[str, Any], now: datetime) -> int:
    """Parse `{seed?}` for POST /api/night/show and return the seed.

    tools/sleepmode sends it; left out, it's tonight's (night_seed). A "sky" key is
    accepted and ignored: older sleepmode processes still running send it, and the
    night view is always the sky now.

    TODO: drop "sky" once no sleepmode process started before the black-page option
    went (2026-11-18) can still be running (after a wake and an MCP restart).
    """
    check_keys(body, ("seed", "sky"), "night request")
    return parse_seed(body["seed"]) if "seed" in body else night_seed(now)


def night_seed(now: datetime) -> int:
    """Tonight's seed: YYYYMMDD of the evening the night began, the same rule as
    tools/sleepmode's night_seed, so the sky is new each night and the same within one."""
    return int((now - _NIGHT_DAY_OFFSET).strftime("%Y%m%d"))


def _parse_marker(raw: Any, label: str) -> Marker:
    data = require_object(raw, label)
    check_keys(data, ("url", "x", "y", "w", "h"), label)
    url = require_str(data.get("url"), f"{label}.url")
    # "//host/..." is protocol-relative, i.e. another origin, and browsers read
    # "/\host" the same way, so no backslashes at all.
    if not url.startswith(_MARKER_URL_PREFIXES) or url.startswith("//") or "\\" in url:
        raise SceneError(f"{label}.url must be a data:image/ URL or a same-origin path")
    return Marker(
        url=url,
        x=require_number(data.get("x"), f"{label}.x"),
        y=require_number(data.get("y"), f"{label}.y"),
        w=require_positive(data.get("w"), f"{label}.w"),
        h=require_positive(data.get("h"), f"{label}.h"),
    )
