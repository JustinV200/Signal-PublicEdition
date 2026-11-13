"""IdleController: the daemon side of the idle view, the board's default when nothing is drawn.

One asyncio loop, ticking every TICK_S:
- the default rule (whiteboard.idle.rules): after [idle] empty_s on an empty items
  view, switch to the idle view (under the night view, only the view it goes back to),
  but not within [idle] ink_quiet_minutes of new ink on the physical board (note_ink,
  fed by InkWatch from the change watcher; ink while the idle view shows blanks it);
- the file sources (LocalSources) every LOCAL_EVERY_S, read only when a file changed;
- weather and news (NetworkSources) as background tasks every weather_min / news_min,
  so a slow network never holds up the loop;
- pushes the page data (BoardController.set_idle) only while the idle view shows, only
  when it really changed, and only on the first tick after a minute boundary, except
  right as the view comes up. The page's clock flips on that boundary anyway, which
  the board already counts as a page change (minute.py), so a push there adds no new
  one: the drift monitor still gets its quiet half-minute (it needs 30 s unchanged),
  and the watcher settles once per minute, not twice.
No model anywhere, and nothing here raises out of the loop: a failing source keeps its
last data and logs once (Outages); anything unexpected is logged and the loop goes on.
"""

import asyncio
import contextlib
import logging
import math
import time
from collections.abc import Callable, Coroutine
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from whiteboard.config import IdleSettings
from whiteboard.daemon.idle.local_sources import IdleFiles, LocalSources
from whiteboard.daemon.idle.network import Lookups, NetworkSources
from whiteboard.daemon.idle.outages import Outages
from whiteboard.display.scene import IDLE_VIEW, ITEMS_VIEW
from whiteboard.display.server import BoardController
from whiteboard.idle import parse_tag_labels, should_go_idle, track_empty

logger = logging.getLogger(__name__)

TICK_S = 1.0
LOCAL_EVERY_S = 15.0
SECONDS_PER_MINUTE = 60.0
# The page's data before any source has answered: every region's empty state.
EMPTY_REGIONS: dict[str, Any] = {
    "usage": None,
    "weather": None,
    "tasks": [],
    "overdue": 0,
    "notes": [],
    "keynotes": [],
    "agents": None,
    "upcoming": [],
    "news": None,
}


def local_now() -> datetime:
    """The local time, aware (the plans, the agenda and the page all use local time)."""
    return datetime.now().astimezone()


@dataclass(frozen=True)
class IdleHooks:
    """The controller's clocks and network calls; tests swap them for fakes.

    Attributes:
        now: Local time now (aware).
        monotonic: Seconds for the default rule and the refresh schedule.
        lookups: The network calls (weather, location, feed).
    """

    now: Callable[[], datetime] = local_now
    monotonic: Callable[[], float] = time.monotonic
    lookups: Lookups = field(default_factory=Lookups)


class IdleController:
    """Keeps the idle view's data fresh and applies the default rule; see the module docstring."""

    def __init__(
        self,
        board: BoardController,
        settings: IdleSettings,
        files: IdleFiles,
        hooks: IdleHooks | None = None,
    ) -> None:
        """Args:
        board: The live board.
        settings: The [idle] section.
        files: Where the sources and caches are.
        hooks: Clocks and network calls; None for the real ones (tests pass fakes).
        """
        hooks = hooks or IdleHooks()
        self._board = board
        self._settings = settings
        self._clock = hooks.now
        self._monotonic = hooks.monotonic
        outages = Outages()
        self._local = LocalSources(files, parse_tag_labels(settings.tag_labels), outages)
        self._network = NetworkSources(settings, files, outages, hooks.lookups)
        self._regions = dict(EMPTY_REGIONS)
        self._empty_since: float | None = None
        # When the change watcher last reported new ink (None: none in this quiet spell).
        self._ink_s: float | None = None
        self._was_showing = False
        # The last tick's wall-clock minute; a new one means the page's clock just flipped.
        self._minute: datetime | None = None
        self._due_s = {"local": -math.inf, "weather": -math.inf, "news": -math.inf}
        self._fetches: dict[str, asyncio.Task[None]] = {}
        self._loop: asyncio.Task[None] | None = None

    @property
    def is_showing(self) -> bool:
        """Whether the page shows the idle view right now."""
        return self._board.scene.view == IDLE_VIEW

    @property
    def is_holding_off(self) -> bool:
        """Whether new ink was reported within ink_quiet_minutes, so the rule waits."""
        if self._ink_s is None:
            return False
        quiet_s = self._settings.ink_quiet_minutes * SECONDS_PER_MINUTE
        return self._monotonic() - self._ink_s < quiet_s

    async def note_ink(self) -> None:
        """The owner drew on the board: blank the idle view (if it shows) so the ink is clear,
        and hold the default rule off until ink_quiet_minutes pass with no new ink."""
        self._ink_s = self._monotonic()
        if self.is_showing:
            # The empty items view is a black page; the board agent may then draw on it.
            await self._board.set_view(ITEMS_VIEW)

    def note_wiped(self) -> None:
        """The board is back to how it was before the ink: the rule may return at once."""
        self._ink_s = None

    async def start(self) -> None:
        """Read the files once, then start the loop (the network sources begin at once)."""
        await self._refresh_local(force=True)
        self._due_s["local"] = self._monotonic() + LOCAL_EVERY_S
        self._loop = asyncio.create_task(self._run())

    async def stop(self) -> None:
        """Cancel the loop and any fetch in flight."""
        tasks = [task for task in (self._loop, *self._fetches.values()) if task is not None]
        for task in tasks:
            task.cancel()
        for task in tasks:
            with contextlib.suppress(asyncio.CancelledError):
                await task

    async def show(self) -> dict[str, Any]:
        """Switch to the idle view (under the night view, the view it goes back to)."""
        await self._push()
        await self._board.set_view(IDLE_VIEW)
        return self.summary()

    async def hide(self) -> dict[str, Any]:
        """Switch back to the projected items. On an empty board the rule returns in empty_s."""
        await self._board.set_view(ITEMS_VIEW)
        return self.summary()

    async def sync(self) -> dict[str, Any]:
        """Re-read every source now, network included, and push if the view shows."""
        await self._refresh_local(force=True)
        await asyncio.gather(self._refresh("weather"), self._refresh("news"))
        if self.is_showing:
            await self._push()
        return self.summary()

    async def tick(self) -> None:
        """One pass of the loop: the default rule, due refreshes, then a push if one is due."""
        now_s = self._monotonic()
        await self._apply_rule(now_s)
        if now_s >= self._due_s["local"]:
            self._due_s["local"] = now_s + LOCAL_EVERY_S
            await self._refresh_local()
        self._start_fetch("weather", now_s, self._settings.weather_min)
        self._start_fetch("news", now_s, self._settings.news_min)
        await self._push_if_due()

    def summary(self) -> dict[str, Any]:
        """Counts per region for the API (no plan or feed text: callers may be a model)."""
        regions = self._regions
        weather = regions["weather"]
        agents = regions["agents"]
        return {
            "ok": True,
            "view": self._board.scene.view,
            "tasks": len(regions["tasks"]),
            "priorities": len(regions["notes"]),
            "keynotes": len(regions["keynotes"]),
            "agents_active": len(agents["active"]) if agents else 0,
            "upcoming": len(regions["upcoming"]),
            "weather": weather["word"] if weather else None,
            "place": weather["place"] if weather else None,
            "headline": regions["news"] is not None,
        }

    async def _run(self) -> None:
        """Tick until cancelled; one bad tick is logged and the next goes on."""
        while True:
            try:
                await self.tick()
            except Exception:
                logger.exception("idle view: a refresh failed; trying again next tick")
            await asyncio.sleep(TICK_S)

    async def _apply_rule(self, now_s: float) -> None:
        """Switch to the idle view once the items view has been empty for empty_s and the
        owner's ink has been quiet (is_holding_off)."""
        if not self._settings.auto:
            return
        self._empty_since = track_empty(self._board.scene, self._empty_since, now_s)
        if self.is_holding_off:
            return
        if should_go_idle(self._empty_since, now_s, self._settings.empty_s):
            self._empty_since = None
            await self._push()
            await self._board.set_view(IDLE_VIEW)

    async def _refresh_local(self, force: bool = False) -> None:
        """Re-read the file sources in a thread, if anything changed."""
        regions = await asyncio.to_thread(self._local.refresh, self._clock(), force)
        if regions is not None:
            self._regions.update(regions)

    def _start_fetch(self, name: str, now_s: float, every_min: float) -> None:
        """Start a background refresh of a network region when it's due and none is running."""
        running = self._fetches.get(name)
        if now_s < self._due_s[name] or (running is not None and not running.done()):
            return
        self._due_s[name] = now_s + every_min * SECONDS_PER_MINUTE
        self._fetches[name] = asyncio.create_task(self._refresh(name))

    async def _refresh(self, name: str) -> None:
        """Refresh one network region; never raises (an unexpected error is logged)."""
        fetch: Callable[[datetime], Coroutine[Any, Any, dict[str, Any] | None]] = (
            self._network.weather if name == "weather" else self._network.news
        )
        try:
            self._regions[name] = await fetch(self._clock())
        except Exception:
            logger.exception("idle view: the %s refresh failed unexpectedly", name)

    async def _push_if_due(self) -> None:
        """Push changed data while the view shows: at once as it comes up, else only on the
        first tick after a minute boundary, together with the page's clock flip."""
        showing = self.is_showing
        came_up = showing and not self._was_showing
        self._was_showing = showing
        minute = self._clock().replace(second=0, microsecond=0)
        after_flip = minute != self._minute
        self._minute = minute
        if showing and (came_up or after_flip):
            await self._push()

    async def _push(self) -> None:
        """Send the current data to the pages, unless they already have exactly this."""
        payload = dict(self._regions)
        if payload == self._board.idle:
            return
        await self._board.set_idle(payload)
