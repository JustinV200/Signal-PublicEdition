"""BoardController: the live scene, display mode and connected pages, in one place.

Both the HTTP API and the in-process daemon (camera calibration, clean capture)
change the board through this class. The scene side (items, fit, views, the night
view) comes from SceneBoard (scene_board.py); this adds what the page shows on top:
the display mode and its markers, highlights, and the TODO and idle views' data, which
the daemon's TodoController and IdleController push after rebuilding it (it isn't saved),
and what the camera should ignore (page_changed_s, motion_masks).

While the night view (sleep mode) shows, nothing may light up the board: every mode
but normal and every highlight is refused, and page_changed_s keeps the camera's
watcher and drift checks paused.
"""

import math
import time
from collections.abc import Sequence
from datetime import datetime
from typing import Any

from whiteboard.display.scene import IDLE_VIEW, NightViewError, SceneError, SceneStore
from whiteboard.display.server.board.idle_ticker import FractionBox, ticker_band_fraction
from whiteboard.display.server.board.minute import last_minute_boundary_s
from whiteboard.display.server.board.modes import (
    DISPLAY_MODES,
    NORMAL_MODE,
    PATTERN_MODE,
    Highlight,
    Marker,
)
from whiteboard.display.server.board.scene_board import (
    DEFAULT_FIT_HEIGHT,
    DEFAULT_PROJECTOR_SIZE,
    SceneBoard,
)


class BoardController(SceneBoard):
    """The scene (SceneBoard) plus the display mode, flashes, and TODO and idle data."""

    def __init__(
        self,
        store: SceneStore,
        projector_size: tuple[int, int] = DEFAULT_PROJECTOR_SIZE,
        fit_height: int = DEFAULT_FIT_HEIGHT,
    ) -> None:
        """Load the saved scene and start in normal mode.

        Args:
            store: Where the scene is persisted.
            projector_size: Projector (width, height) in pixels, from the display bounds.
            fit_height: Logical stage height once a board fit is set.

        Raises:
            OSError: If the scene file exists but can't be read.
        """
        super().__init__(store, projector_size, fit_height)
        self._mode = NORMAL_MODE
        self._markers: tuple[Marker, ...] = ()
        # The TODO view's page data (whiteboard.todo.view.build_payload); None until synced.
        self._todo: dict[str, Any] | None = None
        # The idle view's page data (whiteboard.idle.build_payload); None until built.
        self._idle: dict[str, Any] | None = None

    @property
    def mode(self) -> str:
        """The current display mode, one of DISPLAY_MODES."""
        return self._mode

    def page_changed_s(self) -> float:
        """When the projected page last changed because of the daemon, for the camera.

        The change watcher ignores what it sees for a moment after this, so the
        daemon's own blanks, marker flashes and drawings never wake it.

        Returns:
            Monotonic seconds of the last push to the pages (scene, mode, TODO data;
            a highlight counts until it ends), or math.inf while a mode other than
            normal shows (a blank, the markers, the fit outline) or the night view
            does, which pauses the watcher and the drift monitor all night. While the
            idle view shows, each minute boundary counts too: its clock flips then.
        """
        if self._mode != NORMAL_MODE or self._scene.night is not None:
            return math.inf
        if self._scene.view == IDLE_VIEW:
            return max(self._changed_s, last_minute_boundary_s(time.monotonic(), datetime.now()))
        return self._changed_s

    def motion_masks(self) -> tuple[FractionBox, ...]:
        """Parts of the board the camera's motion check should leave out, for the watcher.

        Returns:
            (x, y, w, h) fractions of the board: the news ticker's band while the idle
            view shows (it scrolls all the time), else none. Flashes and the night view
            need nothing here: page_changed_s already stops the watcher sampling then.
        """
        if self._scene.view != IDLE_VIEW:
            return ()
        stage = self.stage()
        return (ticker_band_fraction(stage["width"], stage["height"]),)

    @property
    def idle(self) -> dict[str, Any] | None:
        """The idle view's data the pages have now, or None before the first push."""
        return self._idle

    def mode_message(self) -> dict[str, Any]:
        """The WebSocket message that tells a page which display mode to show."""
        markers = [vars(marker) for marker in self._markers]
        return {"type": "mode", "mode": self._mode, "markers": markers}

    def todo_message(self, newly_done: Sequence[str] = ()) -> dict[str, Any]:
        """The WebSocket message with the TODO view's data; `newly_done` ids get animated."""
        return {"type": "todo", "todo": self._todo, "newly_done": list(newly_done)}

    def idle_message(self) -> dict[str, Any]:
        """The WebSocket message with the idle view's data."""
        return {"type": "idle", "idle": self._idle}

    def status(self) -> dict[str, Any]:
        """A summary for GET /api/status."""
        return {
            "mode": self._mode,
            "view": self._scene.view,
            "item_count": len(self._scene.items),
            "pages_connected": self.hub.page_count,
            "stage": self.stage(),
        }

    async def set_todo(self, todo: dict[str, Any], newly_done: Sequence[str] = ()) -> None:
        """Replace the TODO view's data and push it to every page. Not saved: it's rebuilt.

        Args:
            todo: JSON-ready data from whiteboard.todo.view.build_payload.
            newly_done: Item ids the page should cross out with the animation.
        """
        self._todo = todo
        await self._broadcast(self.todo_message(newly_done))

    async def set_idle(self, idle: dict[str, Any]) -> None:
        """Replace the idle view's data and push it to every page. Not saved: it's rebuilt.

        Args:
            idle: JSON-ready data from whiteboard.idle.build_payload.
        """
        self._idle = idle
        await self._broadcast(self.idle_message())

    async def set_mode(self, mode: str, markers: tuple[Marker, ...] = ()) -> None:
        """Switch every page's display mode. Markers are only shown in pattern mode.

        Raises:
            SceneError: If `mode` isn't in DISPLAY_MODES.
            NightViewError: A mode other than normal while the night view shows.
        """
        if mode not in DISPLAY_MODES:
            raise SceneError(f"mode must be one of {', '.join(DISPLAY_MODES)}, got {mode!r}")
        if mode != NORMAL_MODE:
            self._refuse_at_night(f"{mode} mode")
        self._mode = mode
        self._markers = markers if mode == PATTERN_MODE else ()
        await self._broadcast(self.mode_message())

    async def highlight(self, box: Highlight) -> None:
        """Flash a bright box on every page. Not part of the saved scene.

        Raises:
            NightViewError: The night view shows.
        """
        self._refuse_at_night("a highlight")
        await self._broadcast({"type": "highlight", **vars(box)}, lasts_s=box.seconds)

    def _refuse_at_night(self, what: str) -> None:
        """Nothing may light up the board under the night view (the error never says to hide it)."""
        if self._scene.night is not None:
            raise NightViewError(
                f"the night view is showing (sleep mode), so {what} is refused until it ends"
            )
