"""BoardAgent: runs one Claude turn per board change, one at a time, coalescing changes mid-turn.

The change watcher calls on_board_changed(); a single worker task works
through at most one pending change at a time. Changes that land while a turn
is running merge into the next turn instead of queueing up. Every change that
passes triage gets a fresh Claude session (connect, turn, optional verify turn,
disconnect, all on the worker task as the SDK requires), so old board images
never pile up in the context.
"""

import asyncio
import contextlib
import logging
from collections.abc import Awaitable, Callable, Mapping, Sequence
from pathlib import Path
from typing import Any, Protocol

from whiteboard.agent.board_change import BoardChange, BoundingBox, merge_changes
from whiteboard.agent.prompt import VERIFY_TEXT
from whiteboard.agent.triage import TriageDecision
from whiteboard.agent.turn_message import build_user_message, user_message

logger = logging.getLogger(__name__)

# Above the 120 s permission dialog, so a turn waiting on the owner isn't cut short.
DEFAULT_TURN_TIMEOUT_S = 300.0

ListItems = Callable[[], Sequence[Mapping]]
"""Returns the scene items currently projected, as dicts."""

TriageFn = Callable[[BoardChange, Sequence[Mapping]], Awaitable[TriageDecision]]
"""Decides whether a change deserves a turn (Triage in production)."""

LookWithProjection = Callable[[], Awaitable[Path]]
"""Photographs the board with the projection on and returns the PNG path."""


class LoadingIndicator(Protocol):
    """The "Claude is thinking" placeholder on the board (LoadingBox in production)."""

    async def show(self, changed: BoundingBox | None) -> None: ...

    async def hide(self) -> None:
        """Remove the placeholder; safe to call when it isn't shown."""
        ...


OnFirstChange = Callable[[], Awaitable[None]]
"""Called once, as soon as a turn's first board-changing tool call succeeds."""


class TurnSession(Protocol):
    """What BoardAgent needs from a Claude session (SdkTurnSession in production)."""

    async def connect(self) -> None: ...

    async def run_turn(
        self, message: dict[str, Any], on_first_change: OnFirstChange | None = None
    ) -> bool:
        """Run one turn; return whether it drew or changed anything on the board."""
        ...

    async def disconnect(self) -> None: ...


class BoardAgent:
    """Reacts to board changes with Claude turns."""

    def __init__(
        self,
        session: TurnSession,
        list_items: ListItems,
        allow_snapshot_read: Callable[[Path], None] = lambda png_path: None,
        triage: TriageFn | None = None,
        look: LookWithProjection | None = None,
        loading: LoadingIndicator | None = None,
        turn_timeout_s: float = DEFAULT_TURN_TIMEOUT_S,
    ) -> None:
        """Create the agent. Nothing runs until start().

        Args:
            session: Opened and closed around each change's turns.
            list_items: Gives the current scene items for each turn's text.
            allow_snapshot_read: Told each turn's snapshot path before the turn, so
                the permission router lets the agent Read exactly that file.
            triage: Cheap pre-check run before each turn; None means every change gets a turn.
            look: Takes a projection-visible photo; a turn that drew is followed by one
                verify turn on it. None turns verification off.
            loading: Shown when a turn starts, hidden when the agent first draws or the
                turn ends (and before the verify look). None means no placeholder.
            turn_timeout_s: A turn (or verify turn) still running after this is given up,
                so a hung CLI can't leave the agent busy forever.
        """
        self._session = session
        self._list_items = list_items
        self._allow_snapshot_read = allow_snapshot_read
        self._triage = triage
        self._look = look
        self._loading = loading
        self._turn_timeout_s = turn_timeout_s
        self._pending: BoardChange | None = None
        self._is_in_turn = False
        # The previous reported snapshot: the "before" for the next change's triage.
        self._last_png: Path | None = None
        self._has_pending = asyncio.Event()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._worker: asyncio.Task[None] | None = None

    @property
    def is_busy(self) -> bool:
        """Whether a change is queued or being worked on (triage included)."""
        return self._pending is not None or self._is_in_turn

    async def start(self) -> None:
        """Start the worker task, which waits for changes."""
        self._loop = asyncio.get_running_loop()
        self._worker = asyncio.create_task(self._run(), name="board-agent")

    async def stop(self) -> None:
        """Cancel any running turn and close the session. Safe to call twice."""
        if self._worker is None:
            return
        worker, self._worker = self._worker, None
        worker.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await worker

    def on_board_changed(
        self, png_path: str | Path, changed_bbox: Sequence[float] | None = None
    ) -> None:
        """Queue a turn for a board change. Safe to call from any thread.

        Args:
            png_path: The clean snapshot taken after the change.
            changed_bbox: (x, y, w, h) of the changed ink, or None if unknown.

        Raises:
            RuntimeError: start() hasn't been called.
        """
        if self._loop is None:
            raise RuntimeError("BoardAgent.start() must run before changes are reported.")
        change = BoardChange(Path(png_path), _as_bbox(changed_bbox), self._last_png)
        self._last_png = change.png_path
        self._loop.call_soon_threadsafe(self._enqueue, change)

    def note_snapshot(self, png_path: str | Path) -> None:
        """Make a snapshot the next change's "before" without taking a turn for it.

        The TODO view handles a cross-out itself; this keeps the next turn's triage
        from seeing that line as new writing. Safe to call from any thread.
        """
        self._last_png = Path(png_path)

    def _enqueue(self, change: BoardChange) -> None:
        """Merge a change into the pending one and wake the worker (runs on the loop)."""
        self._pending = merge_changes(self._pending, change)
        self._has_pending.set()

    async def _run(self) -> None:
        """Worker: take one turn per pending change until cancelled."""
        while True:
            await self._has_pending.wait()
            self._has_pending.clear()
            change, self._pending = self._pending, None
            if change is None:
                continue
            self._is_in_turn = True
            try:
                await self._take_turn(change)
            except Exception:
                # The worker must outlive any one bad change.
                logger.exception("Board agent failed on %s; carrying on", change.png_path)
            finally:
                self._is_in_turn = False

    async def _take_turn(self, change: BoardChange) -> None:
        """Triage a change, then run it (and its verify turn) in a fresh session."""
        items = self._list_items()
        if self._triage is not None:
            decision = await self._triage(change, items)
            if not decision.act:
                logger.info("Triage skipped %s: %s", change.png_path.name, decision.reason)
                return
            logger.info("Triage says act for %s: %s", change.png_path.name, decision.reason)
        # However the turn ends (done, error, cancel), the placeholder must not stay, so
        # show() is inside the try: a cancel right after it still reaches the finally.
        try:
            if self._loading is not None:
                await self._loading.show(change.changed_bbox)
            await self._run_turn(change, items)
        finally:
            await self._hide_loading()

    async def _run_turn(self, change: BoardChange, items: Sequence[Mapping]) -> None:
        """Connect a fresh session, run the turn, then the optional verify turn."""
        try:
            message = build_user_message(change, items)
        except (OSError, ValueError):
            logger.exception("Can't read snapshot %s; skipping this change", change.png_path)
            return
        try:
            await self._session.connect()
        except Exception:
            logger.exception("Board agent couldn't start its Claude session; skipping this change")
            return
        # Always closed, on error or cancel, so no CLI process is left behind.
        try:
            logger.info("Board agent turn for %s", change.png_path.name)
            self._allow_snapshot_read(change.png_path)
            did_change = await self._send(message, self._hide_loading)
            # Hidden before the verify look, so the check doesn't see the placeholder.
            await self._hide_loading()
            if did_change and self._look is not None:
                await self._verify()
        finally:
            await self._disconnect()

    async def _hide_loading(self) -> None:
        """Remove the placeholder; a failure is logged, not raised."""
        if self._loading is None:
            return
        try:
            await self._loading.hide()
        except Exception:
            logger.exception("Board agent couldn't remove the loading box")

    async def _send(
        self, message: dict[str, Any], on_first_change: OnFirstChange | None = None
    ) -> bool:
        """Run one turn. Returns whether it changed the board (False if it failed or hung)."""
        try:
            async with asyncio.timeout(self._turn_timeout_s):
                return await self._session.run_turn(message, on_first_change)
        except TimeoutError:
            # The caller's finally disconnects the session, which ends the stuck CLI.
            logger.warning("Board agent turn gave up after %g s", self._turn_timeout_s)
            return False
        except Exception:
            logger.exception("Board agent turn failed")
            return False

    async def _verify(self) -> None:
        """One follow-up turn, in the same session, on a projection-visible photo."""
        try:
            png_path = await self._look()
            message = user_message(png_path.read_bytes(), VERIFY_TEXT)
        except Exception:
            logger.exception("Board agent verify look failed; skipping the check")
            return
        logger.info("Board agent verify turn for %s", png_path.name)
        self._allow_snapshot_read(png_path)
        await self._send(message)

    async def _disconnect(self) -> None:
        """Close the session; a failure is logged, not raised."""
        try:
            await self._session.disconnect()
        except Exception:
            logger.exception("Board agent session didn't close cleanly")


def _as_bbox(changed_bbox: Sequence[float] | None) -> BoundingBox | None:
    """Normalize the watcher's box to integer (x, y, w, h)."""
    if changed_bbox is None:
        return None
    x, y, w, h = (int(round(value)) for value in changed_bbox)
    return (x, y, w, h)
