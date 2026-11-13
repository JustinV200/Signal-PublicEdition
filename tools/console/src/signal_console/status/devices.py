"""The Connected devices rows: projector, webcam, voice hub, glasses, desktop browser, Docker.

Every row says its state in words (the owner is colourblind; the page adds a
filled or hollow dot as a second cue). Read-only: one whiteboard /api/status
request, the hub state the status watcher already keeps, and a process scan
cached for PROCESS_CACHE_S. The glasses have no status of their own: the
hub opens their mic while it runs, so their row follows the hub's.
"""

import asyncio
import logging
import time
from pathlib import Path
from typing import Any

import aiohttp

from signal_console.paths import BROWSER_PROFILE_DIR, WHITEBOARD_STATE_DIR
from signal_console.status.local_processes import LocalProcesses, scan_processes
from signal_console.status.whiteboard_api import find_whiteboard, get_whiteboard_json

PROCESS_CACHE_S = 10.0
# The whiteboard's views in words (the same words the page's Boards view uses).
VIEW_WORDS = {
    "todo": "the to-do list",
    "idle": "the idle board",
    "items": "your board",
    "night": "the night view",
}

log = logging.getLogger(__name__)

Row = dict[str, Any]


class DeviceReader:
    """Builds the device rows on request; the page polls it while the Devices view is open."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        whiteboard_dir: Path = WHITEBOARD_STATE_DIR,
        browser_profile: Path = BROWSER_PROFILE_DIR,
    ) -> None:
        """Set up; nothing is read until rows()."""
        self._session = session
        self._whiteboard_dir = whiteboard_dir
        self._browser_profile = browser_profile
        self._processes: LocalProcesses | None = None
        self._processes_at = -PROCESS_CACHE_S

    async def rows(self, voice: dict[str, Any]) -> list[Row]:
        """Every device row, in page order.

        Args:
            voice: The status watcher's voice state ({running, phase, startedBy}).
        """
        board = await self._board_status()
        processes = await self._scan()
        return [
            projector_row(board),
            webcam_row(board),
            hub_row(voice),
            glasses_row(voice),
            _row(
                "browser",
                "Desktop browser",
                processes.is_desktop_browser_running,
                ("Running (the Signal Edge profile is open)", "Not running"),
            ),
            _row(
                "docker",
                "Docker (docker browser)",
                processes.is_docker_running,
                ("Docker Desktop is running", "Docker Desktop isn't running"),
            ),
        ]

    async def _board_status(self) -> dict[str, Any] | None:
        target = find_whiteboard(self._whiteboard_dir)
        if target is None:
            return None
        try:
            return await get_whiteboard_json(self._session, target, "/api/status")
        except (aiohttp.ClientError, TimeoutError, ValueError) as error:
            log.debug("whiteboard daemon not answering: %s", error)
            return None

    async def _scan(self) -> LocalProcesses:
        if self._processes is None or time.monotonic() - self._processes_at >= PROCESS_CACHE_S:
            self._processes = await asyncio.to_thread(scan_processes, self._browser_profile)
            self._processes_at = time.monotonic()
        return self._processes


def projector_row(board: dict[str, Any] | None) -> Row:
    """The projector, as the whiteboard daemon sees its board page."""
    if board is None:
        return _row("projector", "Projector", False, ("", "Whiteboard off, nothing projected"))
    pages = board.get("pages_connected")
    pages = pages if isinstance(pages, int) else 0
    if pages < 1:
        return _row("projector", "Projector", False, ("", "Whiteboard on, but no board page open"))
    showing = VIEW_WORDS.get(str(board.get("view")), "the board page")
    return _row("projector", "Projector", True, (f"Projecting {showing}", ""))


def webcam_row(board: dict[str, Any] | None) -> Row:
    """The webcam, with canOpen set when its live stream can be shown."""
    camera = board.get("camera") if board else None
    if board is None:
        row = _row("webcam", "Webcam", None, ("", "Unknown: the whiteboard is off"))
    elif not isinstance(camera, str):
        row = _row("webcam", "Webcam", False, ("", "Not available (the whiteboard has no camera)"))
    else:
        calibrated = "calibrated" if board.get("calibrated") else "not calibrated"
        row = _row("webcam", "Webcam", True, (f"Live, {camera}, {calibrated}", ""))
    return {**row, "canOpen": row["state"] == "on"}


def hub_row(voice: dict[str, Any]) -> Row:
    """The voice hub: running (with its phase) or stopped."""
    if not voice.get("running"):
        return _row("hub", "Voice hub", False, ("", "Stopped"))
    phase = voice.get("phase")
    by = voice.get("startedBy") or "unknown"
    words = f"Running, {phase}" if phase else "Running"
    return _row("hub", "Voice hub", True, (f"{words} (started by {by})", ""))


def glasses_row(voice: dict[str, Any]) -> Row:
    """The glasses, which are in use exactly while the hub runs (it holds their mic open)."""
    if not voice.get("running"):
        return _row("glasses", "Glasses", False, ("", "Not in use (the voice hub is stopped)"))
    return _row("glasses", "Glasses", True, ("In use by the voice hub", ""))


def _row(device_id: str, name: str, is_on: bool | None, words: tuple[str, str]) -> Row:
    """One row; `words` is (when on, when off). is_on None means unknown (the off words)."""
    state = "unknown" if is_on is None else ("on" if is_on else "off")
    return {"id": device_id, "name": name, "state": state, "words": words[0] if is_on else words[1]}
