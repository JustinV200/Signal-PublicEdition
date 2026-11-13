"""InkWatch: tells the idle view when the owner draws on, or wipes, the physical board.

It sits in front of the change watcher's callback (watcher_tasks). The watcher only
reports changes between blank-page captures, so the idle page, its minute flips and every
other page change the daemon makes never reach it. A report is marker ink, erasing, or
daylight and camera noise, and one report can't tell them apart by size: the watcher
re-baselines on every report, so slow writing can arrive as several reports as small as
noise. So InkWatch compares captures itself, counting only ink ADDED (added_ink_ratio;
erasing never counts as new ink):

- New ink: at least [idle] ink_min_ratio (that value included) added since the last ink
  photo of this hold, or, outside a hold, since the reference (the board as last accepted).
  Calls note_ink, which blanks the idle view and starts or extends the hold; the photo
  becomes the last ink photo. Noise during a hold measures against that photo, so it
  never extends the hold.
- Wiped: during a hold, the board is back within ink_min_ratio of the reference (all
  change, ink_change). Calls note_wiped, so the idle view may return at once. Not after a
  calibration or fit change during the hold: the new reference already has the ink on it,
  so only the timer ends that hold.
- After a hold: the board as it is (leftover ink and all) becomes the reference.
- Otherwise the reference stays, so a slow writer's small additions add up, until it's
  REFERENCE_MAX_AGE_S old; then it moves to the capture before this report (its age
  counting from now), so light drift never builds up to ink while this report's change
  can still start a build-up.
Every change then goes on (to the TODO cross-out check and the board agent) unchanged.
The first clean capture, and the first after a calibration or fit change (captures no
longer line up), becomes the reference.
"""

import asyncio
import logging
from collections.abc import Callable
from pathlib import Path

import numpy as np

from whiteboard.camera import BBox, CleanFrame, OnBoardChanged, added_ink_ratio, ink_change
from whiteboard.daemon.idle.controller import IdleController

logger = logging.getLogger(__name__)

# A compare of two clean captures: added_ink_ratio or _changed_ratio.
Measure = Callable[[np.ndarray, np.ndarray], float]

# How long small additions keep adding up against the same reference. A judgment call,
# not measured: the watcher reports a writer's pauses at least 30 s apart
# (min_interval_s), so a few minutes covers slow writing, while light drifts over hours.
REFERENCE_MAX_AGE_S = 300.0


class InkWatch:
    """The watcher's on_board_changed and on_clean_frame for the idle view; see the module."""

    def __init__(
        self, idle: IdleController, ink_min_ratio: float, downstream: OnBoardChanged
    ) -> None:
        """Args:
        idle: The idle view's controller.
        ink_min_ratio: [idle] ink_min_ratio: the added ink, as a fraction of the pixels,
            from which (inclusive) the board counts as having new ink.
        downstream: Where every change goes on to (the cross-out check or the agent).
        """
        self._idle = idle
        self._ink_min_ratio = ink_min_ratio
        self._downstream = downstream
        self._previous: CleanFrame | None = None
        self._latest: CleanFrame | None = None
        self._latest_s = 0.0
        self._reference: CleanFrame | None = None
        self._reference_s = 0.0
        # The last photo judged new ink, while that hold lasts.
        self._ink_photo: CleanFrame | None = None
        # False once a calibration change mid-hold put the ink into the reference.
        self._can_see_wipe = True

    async def on_clean_frame(self, clean: CleanFrame, now_s: float) -> None:
        """Keep the last two clean captures (the watcher calls this before its compare),
        and start a new reference when there's none or captures no longer line up."""
        self._previous, self._latest, self._latest_s = self._latest, clean, now_s
        if not _lines_up(self._reference, clean):
            self._reference, self._reference_s = clean, now_s
            self._ink_photo = None
            self._can_see_wipe = not self._idle.is_holding_off

    async def on_board_changed(self, png_path: Path, changed_bbox: BBox) -> None:
        """Tell the idle view, then pass the change on. An idle failure is logged, never
        keeping the change from the agent."""
        try:
            await self._note_change()
        except Exception:
            logger.exception("idle view: couldn't apply new board ink; passing the change on")
        await self._downstream(png_path, changed_bbox)

    async def _note_change(self) -> None:
        """Apply the module's rules to the latest capture."""
        holding = self._idle.is_holding_off
        if self._ink_photo is not None and not holding:
            self._accept_board()  # the hold is over; leftover ink is the board now
        added = await self._ratio(added_ink_ratio, self._ink_photo or self._reference)
        if added >= self._ink_min_ratio:
            if not holding:
                self._can_see_wipe = True  # a new hold, from a reference without its ink
            self._ink_photo = self._latest
            await self._idle.note_ink()
        elif holding:
            if self._can_see_wipe and await self._is_wiped():
                logger.info("idle view: board ink wiped, the idle view may come back")
                self._idle.note_wiped()
                self._accept_board(self._latest)
        else:
            logger.info("idle view: %.4f ink added since the reference, not ink yet", added)
            if self._latest_s - self._reference_s >= REFERENCE_MAX_AGE_S:
                self._accept_board()

    async def _is_wiped(self) -> bool:
        """Whether the latest capture is back within ink_min_ratio of the reference."""
        return await self._ratio(_changed_ratio, self._reference) < self._ink_min_ratio

    def _accept_board(self, capture: CleanFrame | None = None) -> None:
        """Make `capture` (default: the one before the latest, if it lines up) the
        reference, its age counting from now, and forget the hold's last ink photo."""
        latest = self._latest
        if capture is None:
            lines_up = latest is not None and _lines_up(self._previous, latest)
            capture = self._previous if lines_up else latest
        self._reference, self._reference_s = capture, self._latest_s
        self._ink_photo = None

    async def _ratio(self, measure: Measure, base: CleanFrame | None) -> float:
        """`measure(base, latest)`; 1.0 (counts as ink, never as wiped) without two
        captures that line up."""
        latest = self._latest
        if base is None or latest is None or not _lines_up(base, latest):
            return 1.0
        return await asyncio.to_thread(measure, base.image, latest.image)


def _changed_ratio(previous: np.ndarray, current: np.ndarray) -> float:
    """ink_change's ratio: all changed ink, added and erased."""
    return ink_change(previous, current).ratio


def _lines_up(reference: CleanFrame | None, clean: CleanFrame) -> bool:
    """Whether `clean` can be compared with `reference` (same calibration and size)."""
    return (
        reference is not None
        and clean.calibration is reference.calibration
        and clean.image.shape == reference.image.shape
    )
