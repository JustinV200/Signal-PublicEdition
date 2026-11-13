"""Realigner: re-solve the marker calibration and, if anything moved, move the fit with it.

Runs after two drifted board checks, on the drift monitor's periodic marker
check, and on request (POST /api/align/realign, board_realign, `whiteboard
realign`). Under the capture lock it flashes the markers and solves a new
homography (kept only within [align] max_reprojection_px), photographs the
blank board and works out where the board now is in the camera:

- the detected outline, if it agrees with an independent estimate: the drift
  check's outline, or (no drift reading) where the old fit says it is;
- otherwise the old outline carried over, if the camera hasn't moved, so only
  the projector did. Camera movement is measured against a blank photo kept
  from the last time the alignment was confirmed (camera.ReferencePhoto).

The new fit is that outline through the new homography. Nothing changes unless
the homography or the fit moved by more than drift_px and every check passed;
otherwise the old alignment stays and the result says why. Items are in logical
board px; when the logical width changes they're rescaled to stay in place
(apply.py).
"""

import asyncio
import logging
from dataclasses import dataclass, replace
from typing import Any, NamedTuple

import numpy as np

from whiteboard.camera import (
    Calibration,
    CalibrationError,
    CameraError,
    DriftReading,
    board_quad_in_camera,
    board_quad_in_projector,
    camera_shift_px,
    corner_error,
    detect_board_quad,
    homography_drift_px,
)
from whiteboard.config import AlignSettings
from whiteboard.daemon.camera_hooks import HookContext, grab_raw_frame_locked, solve_markers_locked
from whiteboard.daemon.realign.apply import apply_alignment, flash_toast
from whiteboard.display.scene import Quad, SceneError, parse_quad

logger = logging.getLogger(__name__)

NOTHING_MOVED = "nothing moved"


class RealignRejected(Exception):
    """A re-align step failed; nothing was changed. The message says why."""


class BoardEstimate(NamedTuple):
    """Where the board is in the camera now (camera px), how sure, and how it was found."""

    corners: np.ndarray
    error_px: float
    method: str


@dataclass(frozen=True)
class RealignResult:
    """What a re-align did. Distances are camera px except the reprojection error.

    Attributes:
        ok: False when a step failed and the old alignment was kept.
        changed: Whether a new calibration (and maybe fit) was applied.
        message: What happened, or why not.
        numbers: projector_drift_px, camera_shift_px, reprojection_error_px, and when
            the board was placed, before_px (where the old fit lands vs the board) and
            after_px (the new estimate's cross-check error). Missing when not measured.
    """

    ok: bool
    changed: bool
    message: str
    numbers: dict[str, float | None]

    def to_dict(self) -> dict[str, Any]:
        """JSON-ready, with distances rounded to 0.01."""
        rounded = {key: _rounded(value) for key, value in self.numbers.items()}
        return {"ok": self.ok, "changed": self.changed, "message": self.message, **rounded}


class Realigner:
    """Runs re-aligns for the daemon; one instance shares the reference photo."""

    def __init__(self, context: HookContext, limits: AlignSettings) -> None:
        """Args: context: board, rig, sync, calibration path and reference photo;
        limits: [align]."""
        self._context = context
        self._limits = limits
        self._reference = context.reference

    async def realign(self, drift: DriftReading | None = None) -> RealignResult:
        """Flash the markers, solve, and re-align if something moved.

        Args:
            drift: The last drifted board reading, or None for a marker check.

        Returns:
            The result. On a change, "Re-aligned to board" shows for a few seconds.

        Raises:
            Whatever set_mode raises (e.g. no board page connected).
        """
        numbers: dict[str, float | None] = {}
        async with self._context.rig.lock:
            try:
                changed, message = await self._realign_locked(drift, numbers)
                result = RealignResult(True, changed, message, numbers)
            except RealignRejected as error:
                result = RealignResult(
                    False, False, f"kept the current alignment: {error}", numbers
                )
        level = logging.INFO if result.ok else logging.WARNING
        logger.log(level, "re-align: %s %s", result.message, result.to_dict())
        if result.changed:
            await flash_toast(self._context.board)
        return result

    async def _realign_locked(
        self, drift: DriftReading | None, numbers: dict[str, float | None]
    ) -> tuple[bool, str]:
        """realign() body; the caller holds rig.lock. Fills `numbers` as it measures.

        Returns (changed, message). Raises RealignRejected if a step fails (nothing changed).
        """
        context, limit = self._context, self._limits.drift_px
        old, old_marker = self._current_alignment(drift)
        marker = await self._solve(numbers)
        frame = await _grab(context)
        projector_drift = homography_drift_px(
            old.homography, marker.homography, marker.projector_size
        )
        numbers["projector_drift_px"] = projector_drift
        board = await self._locate_board(frame, old, marker, drift, numbers)
        fit_moves = _should_move_fit(board, old, marker, limit, numbers)
        if projector_drift <= limit and not fit_moves:
            # The old calibration still holds, so this photo shows the room as it saw it.
            # Only the first one counts: refreshing it would let a creeping camera drag
            # the reference along while H stays put.
            if await asyncio.to_thread(self._reference.load, old_marker) is None:
                await asyncio.to_thread(self._reference.save, frame, old_marker)
            return False, NOTHING_MOVED
        if not isinstance(board, BoardEstimate):
            raise RealignRejected(f"the camera or projector moved, but {board}")
        quad = board_quad_in_projector(board.corners, marker.homography) if fit_moves else None
        await _apply(context, marker, _as_quad(quad, old.board_quad))
        await asyncio.to_thread(self._reference.save, frame, marker)
        return True, f"re-aligned ({board.method if fit_moves else 'fit kept'})"

    def _current_alignment(self, drift: DriftReading | None) -> tuple[Calibration, Calibration]:
        """The rig's calibration (with its fit) and the marker calibration, checked usable."""
        self._context.sync.refresh()
        old, old_marker = self._context.rig.calibration, self._context.sync.marker_calibration
        if old is None or old_marker is None or old.board_quad is None:
            raise RealignRejected("not calibrated and fitted yet; run whiteboard calibrate")
        if drift is not None and drift.calibration is not old:
            raise RealignRejected("the alignment changed since the drift check")
        return old, old_marker

    async def _solve(self, numbers: dict[str, float | None]) -> Calibration:
        """Flash the markers and solve; reject a failed or inaccurate solve."""
        try:
            marker = await solve_markers_locked(self._context)
        except (CalibrationError, CameraError) as error:
            raise RealignRejected(f"calibration failed: {error}") from error
        numbers["reprojection_error_px"] = error_px = marker.reprojection_error_px
        limit = self._limits.max_reprojection_px
        if error_px > limit:
            raise RealignRejected(f"reprojection error {error_px:.2f} px is over {limit} px")
        return replace(marker, board_quad=None, board_size=None)

    async def _locate_board(
        self,
        frame: np.ndarray,
        old: Calibration,
        marker: Calibration,
        drift: DriftReading | None,
        numbers: dict[str, float | None],
    ) -> BoardEstimate | str:
        """Where the board is in the camera now, or why that can't be told safely."""
        limit = self._limits.drift_px
        expected = board_quad_in_camera(old.board_quad, old.homography)
        detected = await asyncio.to_thread(detect_board_quad, frame, marker)
        if detected is not None:
            check = drift.detected if drift is not None else expected
            agreement = corner_error(detected, check)
            if agreement <= limit:
                return BoardEstimate(detected, agreement, "detected board outline")
        reference = await asyncio.to_thread(self._reference.load, old)
        shift = None if reference is None else camera_shift_px(reference, frame)
        numbers["camera_shift_px"] = shift
        if shift is None:
            return "there's no reference photo yet to tell whether the camera moved"
        # The carried-over outline is off by about as much as the camera moved.
        if shift > limit / 2:
            return f"the camera moved ({shift:.0f} px) and the board outline wasn't confirmed"
        return BoardEstimate(expected, shift, "fit carried over, only the projector moved")


def _should_move_fit(
    board: BoardEstimate | str,
    old: Calibration,
    marker: Calibration,
    limit: float,
    numbers: dict[str, float | None],
) -> bool:
    """Whether the fit should follow the board estimate; records before_px and after_px.

    Never worse: only when the old fit lands over `limit` off the board under the
    new calibration and the estimate's own error is smaller than that.
    """
    if not isinstance(board, BoardEstimate):
        return False
    landed = board_quad_in_camera(old.board_quad, marker.homography)
    numbers["before_px"] = before = corner_error(landed, board.corners)
    numbers["after_px"] = board.error_px
    return before > limit and board.error_px < before


async def _grab(context: HookContext) -> np.ndarray:
    """A raw blank-page frame, or RealignRejected."""
    try:
        return await grab_raw_frame_locked(context.rig)
    except CameraError as error:
        raise RealignRejected(f"camera problem: {error}") from error


async def _apply(context: HookContext, marker: Calibration, quad: Quad) -> None:
    """apply_alignment, with a failed save turned into RealignRejected."""
    try:
        await apply_alignment(context, marker, quad)
    except OSError as error:
        raise RealignRejected(f"couldn't save the new alignment: {error}") from error


def _as_quad(quad_projector: np.ndarray | None, old_quad: np.ndarray) -> Quad:
    """The new fit as a plain-float scene quad (the old calibration's array when None)."""
    array = old_quad if quad_projector is None else quad_projector
    try:
        return parse_quad(array.tolist())
    except SceneError as error:
        raise RealignRejected(f"the new board outline is unusable: {error}") from error


def _rounded(value: float | None) -> float | None:
    """A distance rounded for JSON."""
    return None if value is None else round(value, 2)
