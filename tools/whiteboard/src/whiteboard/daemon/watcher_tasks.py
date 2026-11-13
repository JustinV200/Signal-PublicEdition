"""Starts the change watcher and what hangs off it: the board agent, the TODO view's
cross-out check, and the drift monitor.

[watcher] enabled runs the ChangeWatcher as a task; [agent] enabled gives
it the board agent as its callback, behind the TODO view's StrikeWatcher: while
the view shows, crossing an item out ticks it instead of waking the agent. With
the agent off, changes are only logged, and no model is ever called, so
cross-outs aren't checked either (the check uses the agent's triage model). [align] auto
adds the DriftMonitor, which checks every watcher capture for drift, uses the
watcher's motion and the agent's state for its idle rule, skips its timed checks
while the watcher finds the room too dark, and re-aligns (and runs its periodic
marker checks) through the Realigner. While it finds the board drifted,
the cross-out check ticks nothing.
Every reported change goes through the idle view's InkWatch first: new ink (at least
[idle] ink_min_ratio of the board in added ink) blanks the idle view and holds
it off until the board is quiet (or wiped), then the change goes on to the cross-out check
or the agent as before.
All stop through the daemon's exit stack (drift monitor, watcher, cross-out checks,
then agent).
"""

import asyncio
import contextlib
import logging
from collections.abc import Callable, Coroutine
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from whiteboard.agent import BoardAgent, Triage, create_board_agent
from whiteboard.camera import (
    BBox,
    BoardActivity,
    CaptureRig,
    ChangeWatcher,
    CleanFrame,
    DriftMonitor,
    OnBoardChanged,
    clean_capture,
    keep_mode,
)
from whiteboard.config import REPO_ROOT, Settings
from whiteboard.daemon.camera_hooks import HookContext
from whiteboard.daemon.idle import IdleController, InkWatch
from whiteboard.daemon.loading_box import LoadingBox
from whiteboard.daemon.realign import Realigner
from whiteboard.daemon.todo import StrikeConfirm, StrikeHooks, StrikeWatcher, TodoController
from whiteboard.display.scene import item_to_dict
from whiteboard.display.server import BoardController

logger = logging.getLogger(__name__)

# Time for a fresh drawing to render and reach the camera before the verify look.
VERIFY_SETTLE_MS = 1500


@dataclass(frozen=True)
class WatchedViews:
    """The views that react to ink on the board.

    Attributes:
        todo: The TODO view, for cross-outs on the board.
        idle: The idle view, blanked by new ink.
    """

    todo: TodoController
    idle: IdleController


async def start_watching(
    context: HookContext,
    realigner: Realigner,
    settings: Settings,
    stack: contextlib.AsyncExitStack,
    views: WatchedViews,
) -> None:
    """Start the watcher, agent, cross-out check and drift monitor that the config enables.

    Args:
        context: The board, the shared capture rig and the calibration state.
        realigner: What the drift monitor re-aligns with.
        settings: [watcher], [agent] and [align] sections.
        stack: Cleanups are registered here.
        views: The TODO and idle views.
    """
    if not settings.watcher.enabled:
        logger.info("change watcher off ([watcher] enabled = false), so no auto re-align either")
        return
    agent = None
    if settings.agent.enabled:
        agent = await _start_agent(context.board, context.rig, settings, stack)
    # The monitor only asks the watcher once running, after `watcher` exists.
    activity = _activity(lambda: watcher.last_motion_s, lambda: watcher.is_room_dark(), agent)
    monitor = _drift_monitor(context.rig, realigner, settings, activity)
    on_board_changed = _log_change
    if agent is not None:
        strikes = _strike_watcher(agent, views.todo, context.rig, settings, monitor)
        stack.push_async_callback(strikes.stop)
        on_board_changed = strikes.on_board_changed
    else:
        logger.info(
            "board agent off ([agent] enabled = false); changes are only logged and "
            "TODO cross-outs aren't checked"
        )
    ink = InkWatch(views.idle, settings.idle.ink_min_ratio, on_board_changed)

    async def on_clean_frame(clean: CleanFrame, now_s: float) -> None:
        await ink.on_clean_frame(clean, now_s)
        if monitor is not None:
            await monitor.on_clean_frame(clean, now_s)

    watcher = ChangeWatcher(context.rig, settings.watcher, ink.on_board_changed, on_clean_frame)
    _start_task(watcher.run(), "change-watcher", stack)
    if monitor is not None:
        _start_task(monitor.run(), "drift-monitor", stack)


def _activity(
    last_motion_s: Callable[[], float], is_dark: Callable[[], bool], agent: BoardAgent | None
) -> BoardActivity:
    """The drift monitor's inputs: the watcher's motion and room light, and, if on, the
    agent's state."""
    if agent is None:
        return BoardActivity(last_motion_s, is_dark=is_dark)
    return BoardActivity(last_motion_s, lambda: agent.is_busy, is_dark)


def _drift_monitor(
    rig: CaptureRig, realigner: Realigner, settings: Settings, activity: BoardActivity
) -> DriftMonitor | None:
    """The drift monitor, or None with [align] auto = false."""
    align = settings.align
    if not align.auto:
        logger.info("auto re-align off ([align] auto = false)")
        return None
    logger.info(
        "auto re-align on (photo check every %g s, marker check every %g s, drift over %g px)",
        align.check_s,
        align.marker_check_s,
        align.drift_px,
    )
    return DriftMonitor(rig, align, realigner.realign, activity)


async def _start_agent(
    board: BoardController, rig: CaptureRig, settings: Settings, stack: contextlib.AsyncExitStack
) -> BoardAgent:
    """Start the board agent and register its stop."""
    triage = None
    if settings.agent.triage:
        triage = Triage(settings.agent.triage_model, settings.agent.triage_timeout_s)

    async def look_with_projection() -> Path:
        # Same capture as a clean one, but the page stays as it is (no blanking).
        look_rig = replace(rig, set_mode=keep_mode, blank_ms=VERIFY_SETTLE_MS)
        return (await clean_capture(look_rig))[0]

    agent = create_board_agent(
        settings.agent.model,
        REPO_ROOT,
        lambda: [item_to_dict(item) for item in board.scene.items],
        triage,
        look_with_projection if settings.agent.verify_after_draw else None,
        LoadingBox(board),
        settings.agent.turn_timeout_s,
    )
    await agent.start()
    stack.push_async_callback(agent.stop)
    logger.info(
        "board agent on (model %s, triage %s, verify %s)",
        settings.agent.model or "default",
        settings.agent.triage_model if triage else "off",
        settings.agent.verify_after_draw,
    )
    return agent


def _strike_watcher(
    agent: BoardAgent,
    todo: TodoController,
    rig: CaptureRig,
    settings: Settings,
    monitor: DriftMonitor | None,
) -> StrikeWatcher:
    """The TODO cross-out check in front of the agent, confirming with the triage model.

    It ticks nothing while the drift monitor (if [align] auto is on) finds the board drifted.
    """
    confirm = StrikeConfirm(settings.agent.triage_model, settings.agent.triage_timeout_s)
    hooks = StrikeHooks(agent.note_snapshot, lambda: monitor is not None and monitor.is_drifted)
    strikes = StrikeWatcher(todo, rig, confirm, _feeder(agent), hooks)
    todo.on_shown = strikes.note_view_shown
    return strikes


def _feeder(agent: BoardAgent) -> OnBoardChanged:
    """The watcher callback that hands changes to the agent."""

    async def feed_agent(png_path: Path, changed_bbox: BBox) -> None:
        # Only queues the turn, so the watcher isn't held up while Claude works.
        agent.on_board_changed(png_path, changed_bbox)

    return feed_agent


async def _log_change(png_path: Path, changed_bbox: BBox) -> None:
    """Watcher callback when the agent is off."""
    logger.info("board changed: %s, region %s", png_path, changed_bbox)


def _start_task(
    coroutine: Coroutine[Any, Any, None], name: str, stack: contextlib.AsyncExitStack
) -> None:
    """Run a background loop as a task that the exit stack cancels."""
    stack.push_async_callback(_cancel, asyncio.create_task(coroutine, name=name))


async def _cancel(task: asyncio.Task[None]) -> None:
    """Cancel a background task and wait for it to finish."""
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task
