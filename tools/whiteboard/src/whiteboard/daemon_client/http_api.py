"""DaemonApi: a small blocking JSON client for the daemon's /api/* endpoints.

Used by the MCP server (from worker threads) and the CLI. stdlib urllib keeps
it light; proxies are disabled because the daemon is always on loopback.
Every request carries the X-Signal-Token header the daemon requires.
"""

import http.client
import json
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Mapping
from http import HTTPStatus
from typing import Any

TOKEN_HEADER = "X-Signal-Token"
DEFAULT_TIMEOUT_S = 30.0
# Calibration shows a pattern, captures, then blanks and captures again.
CALIBRATE_TIMEOUT_S = 90.0
STATUS_TIMEOUT_S = 2.0
# The camera stream sends a frame about every 0.2 s, so a long silence means it's stuck.
STREAM_TIMEOUT_S = 10.0


class DaemonUnreachableError(ConnectionError):
    """Nothing answered at the daemon's address; the request was never handled."""


class DaemonApiError(RuntimeError):
    """The daemon answered with an error, or didn't answer in time."""


class DaemonAuthError(DaemonApiError):
    """The daemon answered 403: our token is wrong or stale. It did not act on the request."""


class DaemonApi:
    """Client for one running daemon."""

    def __init__(self, base_url: str, token: str) -> None:
        """Create the client.

        Args:
            base_url: e.g. "http://127.0.0.1:8770".
            token: The API token from .state/token.
        """
        self.base_url = base_url.rstrip("/")
        self._token = token
        # An empty ProxyHandler stops urllib from routing loopback via a system proxy.
        self._opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def has_same_target(self, other: "DaemonApi") -> bool:
        """True if `other` talks to the same address with the same token (never exposes it)."""
        return self.base_url == other.base_url and self._token == other._token

    def status(self) -> dict[str, Any]:
        """GET /api/status (quick timeout, used to probe whether the daemon is up)."""
        return self.request("GET", "/api/status", timeout_s=STATUS_TIMEOUT_S)

    def scene(self) -> dict[str, Any]:
        """GET /api/scene: the projected items."""
        return self.request("GET", "/api/scene")

    def put_item(self, item: Mapping[str, Any]) -> dict[str, Any]:
        """POST /api/items: create an item, or replace the one with the same id."""
        return self.request("POST", "/api/items", item)

    def patch_item(self, item_id: str, fields: Mapping[str, Any]) -> dict[str, Any]:
        """PATCH /api/items/{id}: change some fields of an item."""
        return self.request("PATCH", f"/api/items/{_quote(item_id)}", fields)

    def delete_item(self, item_id: str) -> dict[str, Any]:
        """DELETE /api/items/{id}."""
        return self.request("DELETE", f"/api/items/{_quote(item_id)}")

    def clear(self) -> dict[str, Any]:
        """POST /api/clear: remove every item."""
        return self.request("POST", "/api/clear", {})

    def highlight(self, region: Mapping[str, float]) -> dict[str, Any]:
        """POST /api/highlight with {x, y, w, h, seconds}."""
        return self.request("POST", "/api/highlight", region)

    def look(self, clean: bool, raw: bool = False) -> dict[str, Any]:
        """POST /api/look (board view) or /api/look/raw (whole projector area, no fit).

        Returns {png_path, width, height, space, items, ...}.
        """
        path = "/api/look/raw" if raw else "/api/look"
        return self.request("POST", path, {"clean": clean})

    def calibrate(self) -> dict[str, Any]:
        """POST /api/calibrate: run marker calibration (and board fitting)."""
        return self.request("POST", "/api/calibrate", {}, timeout_s=CALIBRATE_TIMEOUT_S)

    def fit_quad(self, quad: list[list[float]] | None) -> dict[str, Any]:
        """POST /api/fit: set the board quad (projector px), or clear it with None."""
        return self.request("POST", "/api/fit", {"quad": quad})

    def fit_auto(self) -> dict[str, Any]:
        """POST /api/fit/auto: re-detect the board outline with the camera."""
        return self.request("POST", "/api/fit/auto", {}, timeout_s=CALIBRATE_TIMEOUT_S)

    def fit_show(self) -> dict[str, Any]:
        """POST /api/fit/show: project the board outline for a few seconds."""
        return self.request("POST", "/api/fit/show", {})

    def align_check(self) -> dict[str, Any]:
        """POST /api/align/check: {error_px, note, detected, expected}; never re-aligns."""
        return self.request("POST", "/api/align/check", {})

    def realign(self) -> dict[str, Any]:
        """POST /api/align/realign: flash the markers and re-align if anything moved."""
        return self.request("POST", "/api/align/realign", {}, timeout_s=CALIBRATE_TIMEOUT_S)

    def save_board(
        self, name: str, description: str = "", overwrite: bool = False, refresher: str = ""
    ) -> dict[str, Any]:
        """POST /api/saves: save the projected items and (if calibrated) the owner's ink.

        refresher ("tasks", "todo" or "" for none) names what can redraw the board later.
        """
        body: dict[str, Any] = {"name": name, "description": description, "overwrite": overwrite}
        if refresher:
            # Only sent when set, so an older daemon (which refuses unknown keys) still saves.
            body["refresher"] = refresher
        return self.request("POST", "/api/saves", body)

    def list_saves(self) -> dict[str, Any]:
        """GET /api/saves: {saves: [meta]}, newest first."""
        return self.request("GET", "/api/saves")

    def load_board(
        self, name: str, mode: str = "replace", include_ink: bool = True
    ) -> dict[str, Any]:
        """POST /api/saves/load: put a saved board back ("replace" or "overlay")."""
        body = {"name": name, "mode": mode, "include_ink": include_ink}
        return self.request("POST", "/api/saves/load", body)

    def delete_save(self, name: str) -> dict[str, Any]:
        """POST /api/saves/delete: remove a saved board."""
        return self.request("POST", "/api/saves/delete", {"name": name})

    def todo(self, action: str, item: str | None = None) -> dict[str, Any]:
        """POST /api/todo/<action>: sync, show, hide, done or undone (those two need `item`).

        Returns the sync summary (`{view, today, overdue, upcoming, of_note, items, ...}`),
        or `{ok, view}` for hide.
        """
        body = {} if item is None else {"item": item}
        return self.request("POST", f"/api/todo/{_quote(action)}", body)

    def night(self, action: str, sky: bool = True) -> dict[str, Any]:
        """POST /api/night/<action>: show (the night sky, or plain black with sky=False) or hide.

        Returns `{ok, view, seed, sky, previous_view}` for show, `{ok, view}` for hide.
        Show uses tonight's seed, the same one sleep mode sends.
        """
        body = {"sky": sky} if action == "show" else {}
        return self.request("POST", f"/api/night/{_quote(action)}", body)

    def idle(self, action: str) -> dict[str, Any]:
        """POST /api/idle/<action>: show, hide or sync the idle view.

        Returns `{ok, view, tasks, priorities, agents_active, upcoming, weather, place,
        headline}` (counts and flags only).
        """
        return self.request("POST", f"/api/idle/{_quote(action)}", {})

    def shutdown(self) -> dict[str, Any]:
        """POST /api/shutdown: stop the daemon cleanly."""
        return self.request("POST", "/api/shutdown", {})

    def request(
        self,
        method: str,
        path: str,
        body: Mapping[str, Any] | None = None,
        timeout_s: float = DEFAULT_TIMEOUT_S,
    ) -> dict[str, Any]:
        """Send one JSON request and return the decoded JSON object.

        Raises:
            DaemonUnreachableError: Nothing is listening (safe to retry).
            DaemonAuthError: The daemon rejected the token (403); nothing was done.
            DaemonApiError: The daemon returned another error status or timed out.
        """
        try:
            with self._open(method, path, body, timeout_s) as response:
                return _decode_object(response.read())
        except TimeoutError as error:
            # A bare timeout comes from reading the response: the daemon may have acted.
            raise DaemonApiError(f"{method} {path} timed out after {timeout_s:g} s") from error

    def open_camera_stream(self, timeout_s: float = STREAM_TIMEOUT_S) -> http.client.HTTPResponse:
        """GET /api/camera/stream: the raw webcam view as MJPEG (read it with iter_jpeg_parts).

        The token goes in the header like every request, never in the URL. Close
        the returned stream (or use it in a `with`) to end it.

        Args:
            timeout_s: Longest wait for the answer and for each read after it.

        Raises:
            DaemonUnreachableError, DaemonAuthError, DaemonApiError: as for request();
            a 503 means the camera is off or has no live frame, a 429 too many streams.
        """
        path = "/api/camera/stream"
        try:
            return self._open("GET", path, None, timeout_s)
        except TimeoutError as error:
            raise DaemonApiError(f"GET {path} timed out after {timeout_s:g} s") from error

    def _open(
        self, method: str, path: str, body: Mapping[str, Any] | None, timeout_s: float
    ) -> http.client.HTTPResponse:
        """Send one request with the token and return the open response.

        Raises:
            DaemonUnreachableError: Nothing is listening (safe to retry).
            DaemonAuthError: The daemon rejected the token (403); nothing was done.
            DaemonApiError: The daemon returned another error status.
            TimeoutError: No answer within timeout_s (the caller words the error).
        """
        data = None if body is None else json.dumps(body).encode("utf-8")
        headers = {TOKEN_HEADER: self._token, "Content-Type": "application/json"}
        request = urllib.request.Request(
            self.base_url + path, data=data, headers=headers, method=method
        )
        try:
            return self._opener.open(request, timeout=timeout_s)
        except urllib.error.HTTPError as error:
            error_class = DaemonAuthError if error.code == HTTPStatus.FORBIDDEN else DaemonApiError
            raise error_class(_error_text(error)) from error
        except urllib.error.URLError as error:
            # urllib wraps only failures while connecting and sending, so the daemon
            # never saw this request. That includes a connect timeout: on Windows a
            # closed loopback port takes ~2 s to refuse, longer than the status probe.
            raise DaemonUnreachableError(f"no daemon at {self.base_url}: {error.reason}") from error


def _quote(item_id: str) -> str:
    """Escape an item id for use as one URL path segment."""
    return urllib.parse.quote(item_id, safe="")


def _decode_object(raw: bytes) -> dict[str, Any]:
    """Parse a response body that must be a JSON object."""
    try:
        decoded = json.loads(raw or b"{}")
    except ValueError as error:
        raise DaemonApiError("daemon sent a response that isn't JSON") from error
    if not isinstance(decoded, dict):
        raise DaemonApiError("daemon sent JSON that isn't an object")
    return decoded


def _error_text(error: urllib.error.HTTPError) -> str:
    """Turn an HTTP error into "<status>: <the daemon's error message>"."""
    raw = error.read()
    try:
        message = json.loads(raw).get("error") or raw.decode("utf-8", "replace")
    except (ValueError, AttributeError):
        message = raw.decode("utf-8", "replace")
    return f"daemon returned {error.code}: {message or error.reason}"
