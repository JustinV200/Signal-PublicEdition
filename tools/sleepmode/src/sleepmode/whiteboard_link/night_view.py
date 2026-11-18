"""NightViewClient: asks the running whiteboard daemon for its night view, and back again.

This is sleepmode's side of the contract in tools/sleepmode/README.md ("The
whiteboard contract"):

- POST /api/night/show {"seed": int} switches the projector page to the night view,
  a dim night sky.
- POST /api/night/hide {} goes back to the view that showed before.
- GET /api/status says which view shows and how many pages are connected, so sleep
  and the keeper can tell the night view is really on the projector (is_showing).
- POST /api/kiosk/open {} asks the daemon to reopen its projector kiosk when no page
  is connected (the night guard's repair, whiteboard_link.repair).

All carry the daemon's X-Signal-Token. The daemon is found through its own
discovery files (tools/whiteboard/.state/daemon.json and token). This client never
starts the daemon (sleep does, through daemon_start): when it isn't running, or doesn't
have these routes yet (404), every call raises WhiteboardUnavailableError and the caller
falls back. A daemon.json without a running pid fails at once (discovery), without the
~2 s a refused loopback connect takes.
"""

import http.client
import json
import logging
import urllib.error
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from sleepmode.whiteboard_link.discovery import read_live_daemon_info

log = logging.getLogger(__name__)

LOOPBACK_HOST = "127.0.0.1"
TOKEN_HEADER = "X-Signal-Token"
SHOW_PATH = "/api/night/show"
HIDE_PATH = "/api/night/hide"
KIOSK_OPEN_PATH = "/api/kiosk/open"
STATUS_PATH = "/api/status"
NIGHT_VIEW = "night"
TOKEN_FILE = "token"
REQUEST_TIMEOUT_S = 5.0
HTTP_NOT_FOUND = 404
MAX_PORT = 65535
# A night runs from noon to noon, so 01:00 belongs to the night that began the evening before.
_NIGHT_DAY_OFFSET = timedelta(hours=12)


class WhiteboardUnavailableError(RuntimeError):
    """The whiteboard can't show the night view: not running, no such route, or it refused."""


def night_seed(now: datetime) -> int:
    """The night's seed, YYYYMMDD of the evening it started: new each night, stable within one."""
    evening = (now - _NIGHT_DAY_OFFSET).date()
    return evening.year * 10000 + evening.month * 100 + evening.day


class NightViewClient:
    """Talks to the whiteboard daemon's night view routes."""

    def __init__(self, state_dir: Path, timeout_s: float = REQUEST_TIMEOUT_S) -> None:
        """Configure the client. Files are read afresh on every call (the daemon may restart).

        Args:
            state_dir: The whiteboard's .state/ folder (daemon.json and token).
            timeout_s: Per-request timeout.
        """
        self._state_dir = state_dir
        self._timeout_s = timeout_s
        # An empty ProxyHandler keeps loopback requests off any system proxy.
        self._opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def show(self, seed: int) -> None:
        """Switch the projector to the night view, tonight's sky (`seed` from night_seed).

        Raises:
            WhiteboardUnavailableError: The whiteboard couldn't do it.
        """
        self._request(SHOW_PATH, {"seed": seed})

    def hide(self) -> None:
        """Leave the night view for the view shown before it (a no-op outside the night view).

        Raises:
            WhiteboardUnavailableError: The whiteboard couldn't be reached or refused.
        """
        self._request(HIDE_PATH, {})

    def is_showing(self) -> bool:
        """True if the night view is on and a page (the projector's kiosk) shows it.

        Raises:
            WhiteboardUnavailableError: The whiteboard couldn't be reached or refused.
        """
        status = self._request(STATUS_PATH, None)
        pages = status.get("pages_connected")
        return status.get("view") == NIGHT_VIEW and isinstance(pages, int) and pages > 0

    def open_kiosk(self) -> bool:
        """Ask the daemon to reopen its projector kiosk if no page is connected.

        Returns:
            True if it tried to reopen it; False if a page was connected or it's backing off.

        Raises:
            WhiteboardUnavailableError: Not running, refused, or its kiosk is off (409).
        """
        return self._request(KIOSK_OPEN_PATH, {}).get("opened") is True

    def is_daemon_running(self) -> bool:
        """True if daemon.json names a running whiteboard daemon (it may still be starting)."""
        return read_live_daemon_info(self._state_dir) is not None

    def _request(self, path: str, body: dict[str, Any] | None) -> dict[str, Any]:
        """POST body as JSON (GET when None) and return the JSON reply, mapping every failure."""
        port, token = self._find_daemon()
        request = urllib.request.Request(
            f"http://{LOOPBACK_HOST}:{port}{path}",
            data=None if body is None else json.dumps(body).encode("utf-8"),
            method="GET" if body is None else "POST",
            headers={"Content-Type": "application/json", TOKEN_HEADER: token},
        )
        try:
            with self._opener.open(request, timeout=self._timeout_s) as response:
                reply = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            raise WhiteboardUnavailableError(_http_error_text(path, error)) from error
        # URLError, timeouts and resets are all OSError; HTTPException is a garbled reply.
        except (OSError, http.client.HTTPException) as error:
            message = f"the whiteboard daemon isn't answering ({error})"
            raise WhiteboardUnavailableError(message) from error
        except (ValueError, UnicodeDecodeError) as error:
            message = f"the whiteboard sent an unreadable reply to {path}"
            raise WhiteboardUnavailableError(message) from error
        if not isinstance(reply, dict) or reply.get("ok") is not True:
            raise WhiteboardUnavailableError(f"the whiteboard refused {path}: {reply!r}")
        return reply

    def _find_daemon(self) -> tuple[int, str]:
        """The running daemon's port and token, from its discovery files."""
        info = read_live_daemon_info(self._state_dir)
        if info is None:
            raise WhiteboardUnavailableError("the whiteboard daemon isn't running")
        try:
            token = (self._state_dir / TOKEN_FILE).read_text(encoding="utf-8").strip()
        except OSError as error:
            raise WhiteboardUnavailableError("the whiteboard daemon isn't running") from error
        port = info.get("port")
        if not isinstance(port, int) or not 0 < port <= MAX_PORT or not token:
            raise WhiteboardUnavailableError("the whiteboard daemon's discovery files are invalid")
        return port, token


def _http_error_text(path: str, error: urllib.error.HTTPError) -> str:
    """Explain an HTTP error status from the daemon."""
    if error.code == HTTP_NOT_FOUND:
        return f"this whiteboard has no night view yet ({path} returned 404)"
    return f"the whiteboard refused {path} (HTTP {error.code})"
