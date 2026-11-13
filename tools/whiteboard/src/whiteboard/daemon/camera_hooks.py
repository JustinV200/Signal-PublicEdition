"""CameraHooks: the camera-backed actions behind /api/look, /api/calibrate, /api/fit/* and
/api/align/check.

Each returns a JSON-ready dict. Every look goes through camera.clean_capture
on a copy of the shared rig, so snapshot saving and pruning stay in one place:
a projection-visible look uses a no-op blank, and a raw look drops the board fit.
The marker-solve and blank-grab steps are module functions, so the automatic
re-align (realign.py) runs exactly the same ones.
"""

import asyncio
import base64
import json
import logging
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

import numpy as np
from aiohttp import web

from whiteboard.camera import (
    Calibration,
    CalibrationError,
    CameraError,
    CaptureRig,
    ReferencePhoto,
    board_quad_in_projector,
    calibrate,
    check_drift_now,
    clean_capture,
    detect_board_quad,
    grab_clean_frame,
    keep_mode,
    pattern_layout,
    save_calibration,
    view_transform,
)
from whiteboard.daemon.board_view import BoardViewSync, with_board_fit
from whiteboard.display.scene import SceneError, item_to_dict, parse_quad
from whiteboard.display.server import BoardController, Marker

logger = logging.getLogger(__name__)

FIT_MODE = "fit"
NORMAL_MODE = "normal"
# How long `fit show` keeps the board outline up before returning to normal.
FIT_SHOW_S = 10.0
NO_CALIBRATION = "not calibrated yet: run board_calibrate (whiteboard calibrate) first"
BOARD_NOT_FOUND = (
    "couldn't find the whiteboard's outline in the camera image; make sure all four board "
    "edges are in view, or pass the corners by hand (board_fit quad / whiteboard fit --quad)"
)


@dataclass(frozen=True)
class HookContext:
    """What the hooks act on.

    Attributes:
        board: The scene and display mode.
        rig: The shared capture rig (camera, snapshot folder, blank time).
        sync: Keeps the rig's calibration matched to the board fit.
        calibration_path: Where the marker calibration is saved.
        fit_height: Logical board height for a fitted view.
        reference: The re-align's blank photo of the last confirmed alignment.
    """

    board: BoardController
    rig: CaptureRig
    sync: BoardViewSync
    calibration_path: Path
    fit_height: int
    reference: ReferencePhoto


class CameraHooks:
    """The camera-backed endpoint handlers."""

    def __init__(self, context: HookContext) -> None:
        """Args: context: The board, rig and calibration state to act on."""
        self._context = context
        self._show_task: asyncio.Task[None] | None = None

    async def look(self, clean: bool) -> dict[str, Any]:
        """Photograph the board in board coordinates (the fitted view if a fit exists)."""
        self._context.sync.refresh()
        return await self._capture(clean, self._context.rig.calibration)

    async def look_raw(self, clean: bool) -> dict[str, Any]:
        """Photograph the whole projector area, ignoring the fit, to read board corners off.

        Like /api/look, the result lists the projected items (in board coordinates).
        """
        marker = self._context.sync.marker_calibration
        result = await self._capture(clean, with_board_fit(marker, None, self._context.fit_height))
        return {**result, "items": [item_to_dict(item) for item in self._context.board.scene.items]}

    async def calibrate(self) -> dict[str, Any]:
        """Solve the marker calibration, save it, then auto-fit the board outline.

        Holds the rig's capture lock throughout, so the watcher or a look can't
        blank or restore the page while the pattern or the blank photo is up.
        """
        async with self._context.rig.lock:
            return await self._calibrate_locked()

    async def fit_auto(self) -> dict[str, Any]:
        """Find the board outline in a blank-page photo and set it as the fit."""
        async with self._context.rig.lock:
            return await self._fit_auto_locked()

    async def align_check(self) -> dict[str, Any]:
        """Measure the board's drift from the fit with one clean capture. Never re-aligns."""
        self._context.sync.refresh()
        try:
            reading = await check_drift_now(self._context.rig)
        except CameraError as error:
            return {"ok": False, "error": str(error)}
        error_px = reading.error_px
        return {
            "ok": True,
            "error_px": None if error_px is None else round(error_px, 2),
            "note": reading.note,
            "detected": None if reading.detected is None else reading.detected.tolist(),
            "expected": None if reading.expected is None else reading.expected.tolist(),
        }

    async def _calibrate_locked(self) -> dict[str, Any]:
        """calibrate() body; the caller holds rig.lock."""
        board = self._context.board
        try:
            calibration = await solve_markers_locked(self._context)
        except (CalibrationError, CameraError) as error:
            return {"ok": False, "error": str(error)}
        marker_only = replace(calibration, board_quad=None, board_size=None)
        await asyncio.to_thread(save_calibration, marker_only, self._context.calibration_path)
        self._context.sync.set_marker_calibration(marker_only)
        fit = await self._fit_auto_locked(remember_room=True)
        return {
            "ok": True,
            "reprojection_error_px": round(calibration.reprojection_error_px, 2),
            "marker_count": calibration.marker_count,
            "board_found": fit["ok"],
            "board_quad": fit.get("board_quad"),
            "board_error": fit.get("error"),
            "stage": board.stage(),
        }

    async def _fit_auto_locked(self, remember_room: bool = False) -> dict[str, Any]:
        """fit_auto() body; the caller holds rig.lock.

        Args:
            remember_room: Also keep the blank photo as the re-align's reference, right
                after a deliberate recalibration (so it starts from the new calibration).
        """
        marker = self._context.sync.marker_calibration
        if marker is None:
            return {"ok": False, "error": NO_CALIBRATION}
        try:
            frame = await grab_raw_frame_locked(self._context.rig)
        except CameraError as error:
            return {"ok": False, "error": str(error)}
        if remember_room:
            await asyncio.to_thread(self._context.reference.save, frame, marker)
        quad_camera = await asyncio.to_thread(detect_board_quad, frame, marker)
        if quad_camera is None:
            return {"ok": False, "error": BOARD_NOT_FOUND}
        corners = board_quad_in_projector(quad_camera, marker.homography).tolist()
        try:
            quad = parse_quad(corners)
        except SceneError as error:
            return {"ok": False, "error": f"detected board outline is unusable: {error}"}
        await self._context.board.set_fit(quad)
        self._context.sync.refresh()
        return {"ok": True, "board_quad": corners, "stage": self._context.board.stage()}

    async def fit_show(self) -> dict[str, Any]:
        """Project the fit outline for FIT_SHOW_S seconds, then go back to normal."""
        # Under the capture lock, so a capture can't restore "normal" mid-switch.
        async with self._context.rig.lock:
            await self._context.board.set_mode(FIT_MODE)
        if self._show_task is not None:
            self._show_task.cancel()
        self._show_task = asyncio.create_task(self._end_fit_show())
        return {"ok": True, "mode": FIT_MODE, "seconds": FIT_SHOW_S}

    async def status(self) -> dict[str, Any]:
        """Camera and calibration fields for GET /api/status."""
        info = getattr(self._context.rig.camera, "info", None)
        calibration = self._context.rig.calibration
        return {
            "camera": None if info is None else f"{info.width}x{info.height} via {info.backend}",
            "calibrated": calibration is not None,
            "board_fitted": calibration is not None and calibration.board_quad is not None,
        }

    async def _capture(self, clean: bool, calibration: Any) -> dict[str, Any]:
        """Take one snapshot with the given calibration; blank the page only if clean."""
        rig = replace(self._context.rig, calibration=calibration)
        if not clean:
            rig = replace(rig, set_mode=keep_mode, blank_ms=0)
        try:
            png_path, is_rectified = await clean_capture(rig)
        except CameraError as error:
            # A 503 with the reason, so board_look and `whiteboard look` say what's wrong.
            body = json.dumps({"ok": False, "error": f"camera problem: {error}"})
            raise web.HTTPServiceUnavailable(text=body, content_type="application/json") from error
        if is_rectified:
            width, height = view_transform(calibration)[1]
            space = "board coordinates" if calibration.board_quad is not None else "projector px"
            return {"png_path": str(png_path), "width": width, "height": height, "space": space}
        frame = rig.camera.latest()
        height, width = frame.shape[:2] if frame is not None else (None, None)
        note = "Not calibrated: this is the raw camera frame and does not match board_draw. "
        return {
            "png_path": str(png_path),
            "width": width,
            "height": height,
            "space": "raw camera pixels",
            "note": note + NO_CALIBRATION,
        }

    async def _end_fit_show(self) -> None:
        """Return to normal after a fit show, unless something else changed the mode."""
        await asyncio.sleep(FIT_SHOW_S)
        async with self._context.rig.lock:
            if self._context.board.mode == FIT_MODE:
                await self._context.board.set_mode(NORMAL_MODE)


async def solve_markers_locked(context: HookContext) -> Calibration:
    """Flash the marker pattern and solve camera-to-projector. The caller holds rig.lock.

    Raises:
        CalibrationError: Too few markers seen.
        CameraError: The camera stopped delivering frames.
    """
    board = context.board
    return await calibrate(
        context.rig.camera,
        lambda: _show_pattern(board),
        lambda: board.set_mode(NORMAL_MODE),
        board.projector_size,
    )


async def grab_raw_frame_locked(rig: CaptureRig) -> np.ndarray:
    """Blank the page and take one camera-px frame. The caller holds rig.lock.

    Raises:
        CameraError: The camera is stale or no fresh frame arrived.
    """
    # rig.lock is already held here and isn't reentrant, so this one grab gets a
    # private lock. calibration=None skips rectifying, which nobody needs here.
    raw_rig = replace(rig, calibration=None, lock=asyncio.Lock())
    return (await grab_clean_frame(raw_rig)).raw


async def _show_pattern(board: BoardController) -> None:
    """Put the page into pattern mode with the ArUco tiles as inline PNGs."""
    markers = tuple(
        Marker(_png_data_url(tile["png_bytes"]), tile["x"], tile["y"], tile["size"], tile["size"])
        for tile in pattern_layout(board.projector_size)
    )
    await board.set_mode("pattern", markers)


def _png_data_url(png: bytes) -> str:
    """A data: URL the board page can show without another request."""
    return "data:image/png;base64," + base64.b64encode(png).decode("ascii")
