"""Run the console server in the foreground (`console serve`) until it's stopped.

It binds 127.0.0.1:<port>, then writes .state/local-key and .state/daemon.json
(so a server that fails to bind never clobbers a running one's files), and
polls status and the task list until cancelled. On a clean exit it removes daemon.json if that
still names this process.
"""

import asyncio
import logging
import os
import time
from pathlib import Path

import aiohttp
import psutil
from aiohttp import web
from signal_brief import BriefPaths

from signal_console.models import ModelFiles
from signal_console.paths import (
    DAEMON_FILE,
    HISTORY_FILE,
    LOCAL_KEY_FILE,
    LOOPBACK_HOST,
    REPO_ROOT,
    TASKS_FILE,
    USAGE_FILE_PATH,
    WHITEBOARD_STATE_DIR,
)
from signal_console.server.action_runner import ActionRunner
from signal_console.server.app import build_app
from signal_console.server.dispatch import Dispatcher
from signal_console.server.events import EventHub
from signal_console.server.security import SessionAuth
from signal_console.server.services import Services
from signal_console.server.tasks_feed import TasksFeed
from signal_console.server.watcher import StatusWatcher
from signal_console.setup_cli import SetupRunner, default_prefix
from signal_console.state_files import (
    ensure_state_dir,
    new_secret,
    read_json,
    write_json,
    write_secret,
)
from signal_console.status import DeviceReader

SHUTDOWN_TIMEOUT_S = 2.0

log = logging.getLogger(__name__)


async def serve(port: int, state_dir: Path, web_dir: Path) -> None:
    """Serve the console until cancelled (Ctrl+C or the process being stopped).

    Args:
        port: The loopback port to listen on.
        state_dir: The console's .state folder.
        web_dir: The built frontend folder.

    Raises:
        OSError: The port couldn't be bound (another console server is probably running).
    """
    ensure_state_dir(state_dir)
    local_key = new_secret()
    events = EventHub(state_dir / HISTORY_FILE)
    async with aiohttp.ClientSession() as session:
        model_files = ModelFiles.for_repo(state_dir)
        status = StatusWatcher(events, state_dir, session, model_files=model_files)
        dispatcher = Dispatcher(events, state_dir)
        tasks = TasksFeed(events, state_dir / TASKS_FILE, USAGE_FILE_PATH)
        services = Services(
            events,
            SessionAuth(),
            status,
            dispatcher,
            ActionRunner(events, state_dir, status),
            local_key,
            tasks,
            DeviceReader(session),
            session,
            WHITEBOARD_STATE_DIR,
            BriefPaths(),
            model_files,
            SetupRunner(default_prefix(REPO_ROOT), REPO_ROOT),
        )
        runner = web.AppRunner(
            build_app(services, web_dir), access_log=None, shutdown_timeout=SHUTDOWN_TIMEOUT_S
        )
        await runner.setup()
        try:
            await web.TCPSite(runner, LOOPBACK_HOST, port).start()
            # The key goes in before daemon.json, so a caller that finds the port finds the key.
            write_secret(state_dir / LOCAL_KEY_FILE, local_key)
            daemon = {
                "pid": os.getpid(),
                # Lets callers tell this server from a stale record (local_api.server_port).
                "createTime": psutil.Process().create_time(),
                "port": port,
                "startedAt": time.time(),
            }
            write_json(state_dir / DAEMON_FILE, daemon)
            log.info("Signal console on http://%s:%d/", LOOPBACK_HOST, port)
            await asyncio.gather(status.run(), tasks.run())
        finally:
            _forget_daemon(state_dir)
            await runner.cleanup()


def _forget_daemon(state_dir: Path) -> None:
    daemon = read_json(state_dir / DAEMON_FILE)
    if daemon is not None and daemon.get("pid") == os.getpid():
        (state_dir / DAEMON_FILE).unlink(missing_ok=True)
