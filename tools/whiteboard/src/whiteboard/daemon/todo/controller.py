"""TodoController: the daemon side of the TODO view.

It reads this and next week's plans from life/, works out what changed since the
last sync (whiteboard.todo.view.track), lays the view out for the current board
size with today's keynotes (whiteboard.keynotes) under the header, and pushes it to
the page through BoardController. Showing the view syncs
first-thing, so newly done items animate in front of the owner.

It also makes the whiteboard's one kind of write to life/: ticking or unticking an
item's checkbox (set_line_done), when an item is marked done or undone through the
API or by a confirmed cross-out on the board. Each such edit is logged, and appended
to .state/todo.log. One lock keeps syncs and edits in order.

A cross-out is matched against the rows that were on the page while it was drawn,
so the controller counts layout generations: one starts whenever the rows on the
page move or change (strike_rows.row_spots), and whenever the page switches to this
view (the owner may have drawn on the items view since).
"""

import asyncio
import logging
from collections.abc import Callable, Collection, Sequence
from datetime import date, datetime
from typing import Any

from whiteboard.daemon.todo.audit import AuditLog
from whiteboard.daemon.todo.files import TodoFiles
from whiteboard.daemon.todo.strike_rows import open_targets, row_spots
from whiteboard.daemon.todo.summary import empty_note, sync_summary
from whiteboard.display.scene import ITEMS_VIEW, TODO_VIEW
from whiteboard.display.server import BoardController
from whiteboard.keynotes import read_keynotes
from whiteboard.todo import (
    HeaderText,
    PlanEditError,
    PlanEntry,
    StrikeTarget,
    TodoGroup,
    TodoLayout,
    TodoStore,
    TrackResult,
    WeekPlan,
    build_groups,
    build_payload,
    find_entries,
    layout_todo,
    long_day_label,
    read_week_entries,
    set_line_done,
    track,
)

logger = logging.getLogger(__name__)

# Who ticked an item, for the log, when the owner crossed it out on the board.
STRIKE_SOURCE = "board cross-out"


class TodoController:
    """Syncs the TODO view from life/ and ticks items; see the module docstring."""

    def __init__(
        self,
        board: BoardController,
        files: TodoFiles,
        clock: Callable[[], datetime] = datetime.now,
    ) -> None:
        """Args:
        board: The live board the view is pushed to.
        files: life/ and the state files.
        clock: Local time now; tests pass a fixed one.
        """
        self._board = board
        self._files = files
        self._clock = clock
        self._store = TodoStore(files.state_path)
        self._tracking = self._store.load()
        self._audit = AuditLog(files.audit_path, files.life_dir.parent, clock)
        self._lock = asyncio.Lock()
        self._groups: list[TodoGroup] = []
        self._result: TrackResult | None = None
        self._layout: TodoLayout | None = None
        self._header = HeaderText("", "")
        self._keynotes: tuple[str, ...] = ()
        # Items with an unsure cross-out, and the day the hint went up.
        self._hints: dict[str, date] = {}
        self._generation = 0
        # Called when show() puts the view up; the StrikeWatcher takes its "before" then.
        self.on_shown: Callable[[], None] = lambda: None

    @property
    def is_showing(self) -> bool:
        """Whether the page shows the TODO view right now."""
        return self._board.scene.view == TODO_VIEW

    @property
    def layout_generation(self) -> int:
        """Goes up whenever the rows on the page move or change, or the page switches to
        this view (see the module docstring). Ticking an item doesn't change it."""
        return self._generation

    async def start(self) -> None:
        """First sync at daemon start; a broken life/ is logged, not fatal."""
        try:
            await self.sync()
        except (OSError, UnicodeDecodeError) as error:
            logger.error("TODO view: can't read life/ (%s); it stays empty until a sync", error)

    async def sync(self) -> dict[str, Any]:
        """Re-read life/ and push the view. Returns a summary (see summary.sync_summary).

        Raises:
            OSError, UnicodeDecodeError: A plan can't be read.
        """
        async with self._lock:
            return await self._sync()

    async def show(self) -> dict[str, Any]:
        """Switch the page to the TODO view, then sync so fresh changes animate on screen.

        A switch that puts the view up (not under the night view) then calls on_shown.
        """
        is_switch = not self.is_showing
        if is_switch:
            # Before the switch, so no snapshot of ink drawn on the items view is ever
            # seen with this view showing and the old generation.
            self._generation += 1
        await self._board.set_view(TODO_VIEW)
        summary = await self.sync()
        if is_switch and self.is_showing:
            self.on_shown()
        return summary

    async def hide(self) -> dict[str, Any]:
        """Switch back to the projected items, exactly as they were.

        Under the night view the items wait under it, so the reply says "night".
        """
        await self._board.set_view(ITEMS_VIEW)
        return {"ok": True, "view": self._board.scene.view}

    async def set_done(
        self, ref: str, is_done: bool, source: str, by_text: bool = True
    ) -> dict[str, Any]:
        """Tick (or untick) the item `ref` names in its plan, then sync.

        The plans are read fresh and the item found by id, so a line edited since the
        last sync is still found if its tag and text (the id) are the same.

        Args:
            ref: An item id or a unique piece of its text (see find_entries).
            is_done: True for done, False to undo.
            source: Who asked, for the log ("api", STRIKE_SOURCE).
            by_text: False to accept only an exact item id.

        Raises:
            TodoLookupError: `ref` matches no item, or several.
            PlanEditError: The plan changed during the edit (the line is gone or now
                there twice), or it can't be written. The view is still synced first.
        """
        async with self._lock:
            today = self._clock().date()
            all_entries, plans = await asyncio.to_thread(
                read_week_entries, self._files.life_dir, today
            )
            entries = find_entries(all_entries, ref, by_text)
            try:
                changed = await asyncio.to_thread(
                    self._write_marks, entries, plans, is_done, source
                )
            finally:
                # A multi-line item can fail part-way, after some lines were written:
                # sync anyway, so the page shows what life/ now says.
                summary = await self._sync()
        item = {"id": entries[0].id, "tag": entries[0].tag, "text": entries[0].text}
        return {**summary, "item": item, "changed": changed}

    async def mark_struck(self, item_ids: Collection[str]) -> None:
        """Mark the items the owner crossed out on the board as done.

        An item that can't be ticked (its line changed meanwhile) is logged and gets
        the "done?" hint instead, so the cross-out isn't silently dropped.
        """
        failed: list[str] = []
        for item_id in item_ids:
            try:
                # By id only: a stray text match must never tick a different item.
                await self.set_done(item_id, True, STRIKE_SOURCE, by_text=False)
            except (LookupError, PlanEditError) as error:
                logger.warning("TODO view: couldn't mark crossed-out item %s: %s", item_id, error)
                failed.append(item_id)
        if failed:
            await self.add_hints(failed)

    async def add_hints(self, item_ids: Collection[str]) -> None:
        """Show "done?" next to items whose cross-out wasn't certain (until done or tomorrow)."""
        async with self._lock:
            today = self._clock().date()
            self._hints.update(dict.fromkeys(item_ids, today))
            await self._push(())

    async def strike_targets(self, generation: int) -> list[StrikeTarget]:
        """The open rows, for the cross-out check, if the view still shows layout `generation`.

        Args:
            generation: The layout_generation the cross-out was drawn under.

        Returns:
            The rows (strike_rows.open_targets), or [] if the view isn't showing or its
            rows changed since. If the board's size changed since the last layout (a
            re-align), it's laid out again and pushed first, so the page is right; that
            is a new generation, so the cross-out gets no rows.
        """
        async with self._lock:
            if self._layout is None or self._result is None:
                return []
            if self._layout.stage != self.board_size():
                self._set_layout(layout_todo(self._groups, self.board_size(), self._keynotes))
                await self._push(())
            if generation != self._generation or not self.is_showing:
                return []
            return open_targets(self._layout, self._result.done_ids)

    async def _sync(self) -> dict[str, Any]:
        """The sync itself; the caller holds the lock."""
        now = self._clock()
        today = now.date()
        entries, plans = await asyncio.to_thread(read_week_entries, self._files.life_dir, today)
        result = track(entries, self._tracking, today)
        await asyncio.to_thread(self._store.save, result.tracking)
        self._tracking, self._result = result.tracking, result
        self._hints = {
            item: day
            for item, day in self._hints.items()
            if day == today and item not in result.done_ids
        }
        self._groups = build_groups(entries, today, result.hidden_ids)
        note = empty_note(self._groups, plans, today)
        self._header = HeaderText(long_day_label(today), f"synced {now:%H:%M}", note)
        keynotes_path = self._files.keynotes_path
        if keynotes_path is not None:
            self._keynotes = await asyncio.to_thread(read_keynotes, keynotes_path, today)
        self._set_layout(layout_todo(self._groups, self.board_size(), self._keynotes))
        await self._push(sorted(result.newly_done))
        if result.newly_done:
            logger.info("TODO view: %d item(s) newly done", len(result.newly_done))
        sources = (plans, self._files.life_dir.parent)
        summary = sync_summary(self._layout, self._groups, result, sources)
        return {"ok": True, "view": self._board.scene.view, "today": today.isoformat(), **summary}

    def _set_layout(self, layout: TodoLayout) -> None:
        """Keep a new layout; one whose rows moved or changed starts a new generation."""
        if self._layout is None or row_spots(layout) != row_spots(self._layout):
            self._generation += 1
        self._layout = layout

    async def _push(self, newly_done: Sequence[str]) -> None:
        """Send the current layout to the page."""
        if self._layout is None or self._result is None:
            return
        payload = build_payload(self._layout, self._header, self._result.done_ids, self._hints)
        await self._board.set_todo(payload, newly_done)

    def _write_marks(
        self,
        entries: Sequence[PlanEntry],
        plans: Sequence[WeekPlan],
        is_done: bool,
        source: str,
    ) -> bool:
        """Set the checkbox on every line of one item (worker thread). True if any changed.

        Args:
            entries: The item's lines.
            plans: This and next week's plans, the only files that may change.
            is_done: Tick or untick.
            source: Who asked, for the audit log.

        Raises:
            PlanEditError: A line isn't in those plans, changed, or can't be written.
        """
        allowed = {plan.path for plan in plans}
        changed = False
        for entry in entries:
            # Entries only ever come from these plans; checked again because this writes life/.
            if entry.source.path not in allowed:
                raise PlanEditError(f"refusing to edit {entry.source.path}: not a current plan")
            if set_line_done(entry.source, is_done, self._files.life_dir):
                changed = True
                self._audit.record("done" if is_done else "undone", entry, source)
        return changed

    def board_size(self) -> tuple[float, float]:
        """The board's current (width, height) in board pixels."""
        stage = self._board.stage()
        return (float(stage["width"]), float(stage["height"]))
