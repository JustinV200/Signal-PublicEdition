"""StrikeWatcher: crossing an item out on the real board, while the TODO view shows, ticks it.

It sits between the change watcher and the board agent. For each board change it
keeps the previous snapshot as "before", with what the board was when it was
reported: the rig's calibration, whether the TODO view showed, and the view's layout
generation (TodoController.layout_generation). The change is only checked when the
view showed, with the same rows and calibration, at both snapshots, so the ink
between them was drawn over the rows it's matched against. A re-align or new fit
replaces the calibration, so old ink would look new; a sync that moved rows, or a
switch into the view, starts a new generation: those changes go straight on, like
one whose capture the drift monitor found over [align] drift_px (a camera bump not
yet re-aligned for). Since the change before a switch into the view (or a daemon
restart) can't be the "before", showing the view takes a fresh clean capture as the
"before" (note_view_shown), so the first line drawn under the list is checked too.
Otherwise (and with snapshots in board pixels), it:
1. finds the open rows that newly added ink runs through (whiteboard.todo.strikes),
   reading the rows of that generation, or none if they've changed since;
2. checks no ink was erased near the rows (strike_checks.looks_shifted): a cross-out
   only adds ink, while old ink shifted by a camera bump erases where it was;
3. takes one frame with the list projected and asks the triage model to confirm the
   ink runs through each item's projected words (strike_confirm.py);
4. ticks the confirmed items in life/ (the page animates them) and puts a "done?"
   hint on the unsure ones, and on a confirmed one whose neighbour reads the same
   (strike_checks.demote_twins); nothing is ticked on doubt.
A change with no crossed-out rows, ink erased near the rows, or ink outside the boxes
of the rows the check confirmed (or was unsure about) goes on to the board agent as
usual, and each reason it wasn't checked or found nothing is logged. Only added ink
is checked for cross-outs: wiping one off the board never un-completes an item
(board_todo_undone does).

The check runs as a background task so the watcher isn't held up by the model call.
"""

import asyncio
import contextlib
import logging
from collections.abc import Callable, Coroutine, Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

import numpy as np

from whiteboard.camera import (
    BBox,
    Calibration,
    CameraError,
    CaptureRig,
    OnBoardChanged,
    added_and_erased_ink,
    clean_capture,
    grab_clean_frame,
    keep_mode,
)
from whiteboard.daemon.todo.controller import TodoController
from whiteboard.daemon.todo.strike_checks import (
    demote_twins,
    is_board_sized,
    is_inside,
    looks_shifted,
    read_pair,
)
from whiteboard.daemon.todo.strike_confirm import StrikeConfirm, StrikeVerdict
from whiteboard.todo import StrikeTarget, strike_candidates

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class StrikeHooks:
    """What StrikeWatcher tells and asks the rest of the daemon, besides forwarding.

    Attributes:
        note_snapshot: Tells the agent a handled snapshot is its next "before".
        is_drifted: Whether the drift monitor's latest check that found the board's
            outline was over [align] drift_px (DriftMonitor.is_drifted). Nothing is
            checked then.
    """

    note_snapshot: Callable[[Path], None] = lambda png_path: None
    is_drifted: Callable[[], bool] = lambda: False


@dataclass(frozen=True)
class _Snapshot:
    """A reported snapshot and what the board was when it was reported.

    Attributes:
        png: The clean snapshot.
        calibration: The rig's calibration.
        is_showing: Whether the TODO view showed.
        generation: The TODO view's layout generation.
    """

    png: Path
    calibration: Calibration | None
    is_showing: bool
    generation: int


class StrikeWatcher:
    """The watcher callback in front of the board agent; see the module docstring."""

    def __init__(
        self,
        todo: TodoController,
        rig: CaptureRig,
        confirm: StrikeConfirm,
        forward: OnBoardChanged,
        hooks: StrikeHooks | None = None,
    ) -> None:
        """Args:
        todo: The TODO view (rows, ticking, hints).
        rig: The capture rig; its calibration says whether snapshots are in board px.
        confirm: The model check.
        forward: The next callback (the board agent's feeder, or the log).
        hooks: The agent's "before" and the drift monitor's reading (none by default).
        """
        self._todo = todo
        self._rig = rig
        self._confirm = confirm
        self._forward = forward
        self._hooks = hooks or StrikeHooks()
        self._last: _Snapshot | None = None
        self._lock = asyncio.Lock()
        self._tasks: set[asyncio.Task[None]] = set()

    async def on_board_changed(self, png_path: Path, changed_bbox: BBox) -> None:
        """The change watcher's callback."""
        # Read as the change is reported, a moment after its capture. Residual risk: a
        # line begun in that moment, under rows a sync is just replacing, is matched
        # against the new rows (a re-align in it shows up as shifted, erased ink).
        # TODO: close that window by having the change watcher stamp each capture with
        # the calibration, view and layout_generation at the moment it was taken.
        # TODO: a change forwarded here can reach the agent before an earlier change
        # whose check is still running (it forwards when done), so the agent may see
        # two changes out of order; queue forwards behind running checks to fix it.
        todo = self._todo
        after = _Snapshot(png_path, self._rig.calibration, todo.is_showing, todo.layout_generation)
        before, self._last = self._last, after
        if before is None or not _is_same_list(before, after):
            if after.is_showing:
                logger.info(
                    "TODO cross-out check: no earlier snapshot under these rows and this "
                    "alignment; passing it on"
                )
            await self._forward(png_path, changed_bbox)
            return
        if self._hooks.is_drifted():
            logger.info("TODO cross-out check: the board has drifted; passing it on")
            await self._forward(png_path, changed_bbox)
            return
        self._start(self._check(before.png, after, changed_bbox), "todo-strike")

    def note_view_shown(self) -> None:
        """Take a fresh "before" in the background: the TODO view just went up.

        TodoController.on_shown. Without it, the first change after the switch has only
        a "before" from the items view (or none, after a daemon restart), so the first
        line drawn under the list, usually the cross-out itself, was never checked.
        """
        self._start(self._take_before(), "todo-strike-before")

    async def _take_before(self) -> None:
        """Clean-capture the board as the next change's "before"; a failure is logged."""
        last, todo = self._last, self._todo
        # Read before the capture: anything that changes meanwhile (a re-align, a sync
        # that moves rows) then mismatches the next change, which is the safe way round.
        state = (self._rig.calibration, todo.is_showing, todo.layout_generation)
        try:
            png, _ = await clean_capture(self._rig)
        except Exception as error:
            logger.warning("TODO cross-out check: no fresh snapshot for the list: %s", error)
            return
        # A change reported during the capture is newer; it stays the "before".
        if self._last is last:
            self._last = _Snapshot(png, *state)

    def _start(self, coroutine: Coroutine[Any, Any, None], name: str) -> None:
        """Run a check or capture as a background task that stop() cancels."""
        task = asyncio.create_task(coroutine, name=name)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def stop(self) -> None:
        """Cancel checks still running (daemon shutdown)."""
        for task in list(self._tasks):
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

    async def _check(self, before: Path, after: _Snapshot, changed_bbox: BBox) -> None:
        """Look for cross-outs; hand the change on when there are none (or on any failure)."""
        async with self._lock:
            try:
                is_handled = await self._handle_strikes(before, after, changed_bbox)
            except Exception:
                logger.exception("TODO cross-out check failed on %s; passing it on", after.png.name)
                is_handled = False
        if is_handled:
            self._hooks.note_snapshot(after.png)
        else:
            await self._forward(after.png, changed_bbox)

    async def _handle_strikes(self, before: Path, after: _Snapshot, changed_bbox: BBox) -> bool:
        """Tick or hint crossed-out rows. True if the change was only cross-outs.

        Raises:
            CameraError: No frame with the list projected could be taken.
        """
        # The rows the line was drawn over, or none if a sync or re-fit has moved them
        # since (a previous cross-out's tick syncs too, but ticking moves no row).
        targets = await self._todo.strike_targets(after.generation)
        if not targets:
            return _pass_on("no open rows, or they moved since the line was drawn")
        images = await asyncio.to_thread(read_pair, before, after.png)
        if images is None or not is_board_sized(images[1], self._todo.board_size()):
            return _pass_on("the snapshots can't be read or aren't in board px")
        added, erased = await asyncio.to_thread(added_and_erased_ink, *images)
        candidates = [candidate.target for candidate in strike_candidates(added, targets)]
        if not candidates:
            return _pass_on("the new ink crosses out no open row")
        if looks_shifted(added, erased, targets):
            return _pass_on("ink was erased near the rows too")
        projected = await _grab_projected(self._rig, after.calibration)
        # TODO: check the registration without the model too: find the projected rows'
        # text in `projected` and compare its height with the row boxes, so an alignment
        # off by most of a row is caught even when the model misreads the words.
        verdict = await self._confirm(images[0], images[1], projected, candidates)
        return await self._apply(demote_twins(verdict, candidates), candidates, changed_bbox)

    async def _apply(
        self, verdict: StrikeVerdict, candidates: Sequence[StrikeTarget], changed_bbox: BBox
    ) -> bool:
        """Tick the struck rows and hint the unsure ones. True if the change was only those."""
        logger.info(
            "TODO cross-out check: %d struck, %d unsure (%s)",
            len(verdict.struck),
            len(verdict.unsure),
            verdict.reason,
        )
        if verdict.struck:
            await self._todo.mark_struck(verdict.struck)
        if verdict.unsure:
            await self._todo.add_hints(verdict.unsure)
        # Ink the check called "not a cross-out" (a note over a row) is for the agent to judge.
        struck_or_unsure = {*verdict.struck, *verdict.unsure}
        strikes = [candidate for candidate in candidates if candidate.id in struck_or_unsure]
        # TODO: the owner's call whether to tick only when the whole change stays inside
        # the struck rows' boxes. Today a confirmed row is ticked even when the same change
        # has writing elsewhere (that still goes to the agent). Stricter means a misjudged
        # mixed change can't tick, but a cross-out made together with a note only hints.
        return bool(strikes) and is_inside(changed_bbox, strikes)


def _pass_on(reason: str) -> bool:
    """Log why a change isn't handled as a cross-out. Returns False: it goes to the agent."""
    logger.info("TODO cross-out check: %s; passing it on", reason)
    return False


def _is_same_list(before: _Snapshot, after: _Snapshot) -> bool:
    """Whether the TODO view showed the same rows, under one calibration, at both snapshots.

    Only then is new ink between them a line drawn over these rows, in board px. The
    generation also moves on a switch into the view, so ink drawn on the items view in
    between never counts.
    """
    # `is`, as in ChangeWatcher: only a re-align or fit replaces the calibration object.
    return (
        after.calibration is not None
        and before.calibration is after.calibration
        and before.is_showing
        and after.is_showing
        and before.generation == after.generation
    )


async def _grab_projected(rig: CaptureRig, calibration: Calibration | None) -> np.ndarray:
    """A fresh camera frame with the list projected, rectified like the snapshots.

    Raises:
        CameraError: The camera is stale, no fresh frame came, or it doesn't fit the
            calibration.
    """
    # A clean capture that leaves the page alone. It still waits blank_ms, under the
    # rig's lock: the capture that found this change only just put the list back on.
    look_rig = replace(rig, set_mode=keep_mode, calibration=calibration)
    clean = await grab_clean_frame(look_rig)
    if not clean.is_rectified:
        raise CameraError("the projected frame's size doesn't match the calibration")
    return clean.image
