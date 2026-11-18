"""run_daemon: the `whiteboard serve` process, from startup to a clean Ctrl+C.

Startup order: claim the port, then the API token, projector, scene, the TODO
view's first sync from life/, the idle view's first read and its refresh loop, camera
(optional), the aiohttp app, daemon.json, the Edge kiosk's watchdog (which opens the
kiosk and reopens it whenever it's gone), then the change watcher, board agent and
drift monitor. Claiming the port first means a second `serve` dies before it can
overwrite .state/token or grab the camera. Every step registers its own cleanup on one
AsyncExitStack, so a failure anywhere (or Ctrl+C, or POST /api/shutdown) unwinds in
reverse: drift monitor, watcher, agent, kiosk watchdog, kiosk, daemon.json, the stop
event (ends open camera streams), HTTP server, camera, the idle loop, port.
"""

import asyncio
import contextlib
import logging
import socket
from pathlib import Path

from aiohttp import web

from whiteboard.camera import Camera, CameraError, CaptureRig, ReferencePhoto, load_calibration
from whiteboard.config import (
    AGENDA_FILE,
    CONSOLE_TASKS_FILE,
    LIFE_DIR,
    SLEEPMODE_STATE_FILE,
    STATE_DIR,
    USAGE_FILE,
    Settings,
)
from whiteboard.daemon.board_view import BoardViewSync
from whiteboard.daemon.camera_hooks import CameraHooks, HookContext
from whiteboard.daemon.camera_stream import add_camera_stream_route
from whiteboard.daemon.daemon_routes import add_daemon_routes
from whiteboard.daemon.idle import IdleController, IdleFiles, add_idle_routes
from whiteboard.daemon.kiosk import (
    KioskWatchdog,
    add_kiosk_routes,
    build_kiosk,
    find_projector_monitor,
    projector_size,
)
from whiteboard.daemon.loading_box import LoadingBox
from whiteboard.daemon.night_resume import resume_night
from whiteboard.daemon.realign import Realigner
from whiteboard.daemon.request_guard import build_request_guard
from whiteboard.daemon.save_routes import SaveContext, add_save_routes
from whiteboard.daemon.todo import TodoController, TodoFiles, add_todo_routes
from whiteboard.daemon.watcher_tasks import WatchedViews, start_watching
from whiteboard.daemon_client import create_token, remove_daemon_info, write_daemon_info
from whiteboard.display.scene import SceneStore
from whiteboard.display.server import BoardController, create_app
from whiteboard.keynotes import KEYNOTES_FILE
from whiteboard.saves import SaveStore

logger = logging.getLogger(__name__)

SCENE_FILE = "scene.json"
CALIBRATION_FILE = "calibration.json"
# The re-align's blank photo of the last confirmed alignment (tag next to it as .json).
ALIGN_REFERENCE_FILE = "align-reference.png"
SNAPSHOT_DIR = "snapshots"
BOARDS_DIR = "boards"
TODO_STATE_FILE = "todo.json"
TODO_AUDIT_FILE = "todo.log"
# The idle view's weather and location caches.
IDLE_CACHE_DIR = "idle"
# Never configurable: the API and camera snapshots must not be reachable off this PC.
LOOPBACK_HOST = "127.0.0.1"


async def run_daemon(settings: Settings, state_dir: Path = STATE_DIR) -> None:
    """Run the daemon until Ctrl+C or POST /api/shutdown.

    Args:
        settings: The loaded config.
        state_dir: Where scene, calibration, snapshots, token and logs live.

    Raises:
        OSError: The port is taken (another daemon running?) or state can't be written.
        CalibrationError: calibration.json is invalid (delete it and recalibrate).
    """
    stop = asyncio.Event()
    display = settings.display
    async with contextlib.AsyncExitStack() as stack:
        listener = stack.enter_context(claim_port(display.port))
        token = create_token(state_dir)
        monitor = find_projector_monitor(display)
        board = BoardController(
            SceneStore(state_dir / SCENE_FILE), projector_size(monitor), display.fit_height
        )
        # A loading box left in scene.json by a crash would sit there forever.
        await LoadingBox(board).hide()
        todo = TodoController(
            board,
            TodoFiles(
                LIFE_DIR,
                state_dir / TODO_STATE_FILE,
                state_dir / TODO_AUDIT_FILE,
                state_dir / KEYNOTES_FILE,
            ),
        )
        await todo.start()
        idle = _build_idle(board, settings, state_dir)
        await idle.start()
        stack.push_async_callback(idle.stop)
        camera = await _open_camera(settings, stack)
        hooks, context = _build_camera_parts(board, camera, settings, state_dir)
        rig = context.rig if context is not None else None
        realigner = _build_realigner(context, settings)
        app = _build_app(board, hooks, token, display.port)
        add_daemon_routes(app, hooks, realigner, stop)
        add_save_routes(app, SaveContext(board, SaveStore(state_dir / BOARDS_DIR), rig))
        add_todo_routes(app, todo)
        add_idle_routes(app, idle)
        kiosk = build_kiosk(display, monitor, state_dir, token)
        watchdog = KioskWatchdog(kiosk, lambda: board.hub.page_count) if kiosk else None
        add_kiosk_routes(app, watchdog)
        add_camera_stream_route(app, camera.latest if camera else None, stop)
        await _serve_http(app, listener, stack)
        # Unwinds before the HTTP server, so open camera streams end at once on
        # Ctrl+C too, instead of holding up aiohttp's shutdown.
        stack.callback(stop.set)
        write_daemon_info(state_dir, display.port)
        stack.callback(remove_daemon_info, state_dir)
        logger.info("whiteboard daemon listening on http://%s:%d", LOOPBACK_HOST, display.port)
        # Before the kiosk, so a daemon started mid-night never lights the board.
        await resume_night(board, SLEEPMODE_STATE_FILE)
        if kiosk is not None and watchdog is not None:
            stack.callback(kiosk.close)
            # Stops before the kiosk closes (the stack unwinds in reverse), so it never reopens it.
            watchdog.start(stack)
        if context is not None and realigner is not None:
            views = WatchedViews(todo, idle)
            await start_watching(context, realigner, settings, stack, views)
        await stop.wait()
        logger.info("whiteboard daemon stopping")


def _build_app(
    board: BoardController, hooks: CameraHooks | None, token: str, port: int
) -> web.Application:
    """The aiohttp app with the board routes, the camera hooks (if any) and the token guard."""
    app = create_app(
        board,
        look=hooks.look if hooks else None,
        calibrate=hooks.calibrate if hooks else None,
        status=hooks.status if hooks else None,
        page_token=token,
    )
    # Outermost, so a request without the token never reaches any handler.
    app.middlewares.insert(0, build_request_guard(token, port))
    return app


def _build_idle(board: BoardController, settings: Settings, state_dir: Path) -> IdleController:
    """The idle view's controller, reading life/, the task list, usage and the agenda."""
    files = IdleFiles(
        life_dir=LIFE_DIR,
        todo_state_path=state_dir / TODO_STATE_FILE,
        tasks_path=CONSOLE_TASKS_FILE,
        usage_path=USAGE_FILE,
        agenda_path=AGENDA_FILE,
        cache_dir=state_dir / IDLE_CACHE_DIR,
        keynotes_path=state_dir / KEYNOTES_FILE,
    )
    return IdleController(board, settings.idle, files)


async def _open_camera(settings: Settings, stack: contextlib.AsyncExitStack) -> Camera | None:
    """Open the webcam, or return None (drawing still works) if it can't be opened."""
    camera = Camera(settings.camera)
    try:
        await asyncio.to_thread(camera.open)
    except CameraError as error:
        logger.error("camera unavailable, so look/calibrate/watcher are off: %s", error)
        return None
    stack.callback(camera.close)
    return camera


def _build_camera_parts(
    board: BoardController, camera: Camera | None, settings: Settings, state_dir: Path
) -> tuple[CameraHooks | None, HookContext | None]:
    """Make the capture rig, its calibration sync and the camera hooks (None without a camera)."""
    if camera is None:
        return None, None
    rig = CaptureRig(
        camera=camera,
        set_mode=board.set_mode,
        snapshot_dir=state_dir / SNAPSHOT_DIR,
        blank_ms=settings.capture.blank_ms,
        keep_snapshots=settings.capture.keep_snapshots,
        # Every blank, marker flash and drawing goes through the board, so the
        # watcher never mistakes them for someone at the board.
        page_changed_s=board.page_changed_s,
        # The idle view's news ticker scrolls all the time; it isn't someone drawing.
        motion_masks=board.motion_masks,
    )
    calibration_path = state_dir / CALIBRATION_FILE
    sync = BoardViewSync(
        board, rig, settings.display.fit_height, load_calibration(calibration_path)
    )
    # Every capture switches mode first, so this keeps captures on the current board fit.
    rig.set_mode = sync.set_mode
    reference = ReferencePhoto(state_dir / ALIGN_REFERENCE_FILE)
    context = HookContext(
        board, rig, sync, calibration_path, settings.display.fit_height, reference
    )
    return CameraHooks(context), context


def _build_realigner(context: HookContext | None, settings: Settings) -> Realigner | None:
    """The re-aligner shared by the drift monitor and /api/align/realign (None without a camera)."""
    if context is None:
        return None
    return Realigner(context, settings.align)


def claim_port(port: int) -> socket.socket:
    """Bind the daemon's loopback port exclusively, before touching any shared state.

    Raises:
        OSError: The port is taken, normally by a daemon that's already running.
    """
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        # Windows lets a socket with SO_REUSEADDR steal a plain bind; this forbids it.
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        listener.bind((LOOPBACK_HOST, port))
    except OSError:
        listener.close()
        raise
    return listener


async def _serve_http(
    app: web.Application, listener: socket.socket, stack: contextlib.AsyncExitStack
) -> None:
    """Start the aiohttp server on the already-bound socket and register its shutdown."""
    # No access log: it wrote the kiosk's ?token= URL to daemon.log and was
    # nearly all of the log (the console polls every 10 s).
    runner = web.AppRunner(app, access_log=None)
    await runner.setup()
    stack.push_async_callback(runner.cleanup)
    await web.SockSite(runner, listener).start()
