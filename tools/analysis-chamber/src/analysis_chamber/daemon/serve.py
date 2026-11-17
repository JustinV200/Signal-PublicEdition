"""serve and start_daemon: bring the daemon up, resume interrupted runs, and shut it down.

Startup order: take the daemon lock (one daemon per state_dir), resume runs from
disk, bind 127.0.0.1 on a random port, then write daemon.json with a fresh token
(so clients never see a token for a port that isn't listening). Shutdown first
stops active runs without marking them cancelled (they resume next start), then
stops the server and its in-flight handlers, removes daemon.json and frees the lock.
"""

import asyncio
import logging
import os
import secrets
from dataclasses import dataclass
from typing import BinaryIO

from analysis_chamber.config import ChamberConfig
from analysis_chamber.daemon.api import ApiServer, start_server
from analysis_chamber.daemon.backend import Backend
from analysis_chamber.daemon.engine import Chamber
from analysis_chamber.daemon.logs import setup_logging
from analysis_chamber.daemon.process import (
    hold_daemon_lock,
    join_kill_on_close_job,
    release_daemon_lock,
)
from analysis_chamber.daemon.state_file import (
    LOOPBACK_HOST,
    DaemonState,
    remove_state,
    write_state,
)
from analysis_chamber.daemon.wiring import default_backend

logger = logging.getLogger(__name__)

TOKEN_BYTES = 32


@dataclass
class RunningDaemon:
    """A started daemon.

    Attributes:
        api: The HTTP server (`api.port` is the loopback port).
        chamber: Its run registry.
        token: The bearer token in daemon.json.
        config: Its config.
        lock: The held state_dir/daemon.lock file.
    """

    api: ApiServer
    chamber: Chamber
    token: str
    config: ChamberConfig
    lock: BinaryIO

    @property
    def port(self) -> int:
        """The loopback port it listens on."""
        return self.api.port

    async def close(self) -> None:
        """Stop runs (they resume next start), then the server, then remove daemon.json.

        daemon.json and the lock go even if stopping fails, so a new daemon can start.
        """
        try:
            await _stop(self.chamber, self.api)
        finally:
            try:
                remove_state(self.config.state_dir, self.token)
            finally:
                release_daemon_lock(self.lock)


async def start_daemon(config: ChamberConfig, backend: Backend) -> RunningDaemon:
    """Lock, resume runs, listen and publish daemon.json.

    Args:
        config: Chamber config (roots, state_dir, max_parallel_runs).
        backend: The phase functions (default_backend in production, fakes in tests).

    Returns:
        The running daemon; call `close()` to stop it.

    Raises:
        DaemonRunningError: Another daemon holds state_dir/daemon.lock.
        OSError: The port couldn't be bound or daemon.json couldn't be written.
    """
    lock = hold_daemon_lock(config.state_dir)
    chamber: Chamber | None = None
    api: ApiServer | None = None
    try:
        chamber = Chamber(config, backend)
        chamber.resume()  # may already have started runs
        token = secrets.token_urlsafe(TOKEN_BYTES)
        api = await start_server(chamber, token)
        write_state(config.state_dir, DaemonState(port=api.port, token=token, pid=os.getpid()))
    except BaseException:
        # Undo what started (runs resume next time), then free the lock.
        try:
            await _stop(chamber, api)
        finally:
            release_daemon_lock(lock)
        raise
    logger.info("analysis-chamber daemon listening on %s:%d", LOOPBACK_HOST, api.port)
    return RunningDaemon(api, chamber, token, config, lock)


async def _stop(chamber: Chamber | None, api: ApiServer | None) -> None:
    """Stop the runs (without marking them cancelled), then the server; either may be None."""
    try:
        if chamber is not None:
            await chamber.shutdown()
    finally:
        if api is not None:
            await api.close()


def serve(config: ChamberConfig) -> None:
    """Run the daemon until interrupted (`analysis-chamber serve`).

    Args:
        config: Chamber config.
    """
    setup_logging(config.log_dir)
    # Agent CLIs must die with the daemon, or an orphan forks a session transcript.
    # The job handle is never closed, so it lives exactly as long as the process.
    # TODO: optionally sweep claude.exe processes left by a previous daemon (check the image
    # name) before resuming; it needs each CLI's pid recorded per run, which nothing does yet.
    join_kill_on_close_job()
    asyncio.run(_serve_forever(config))


async def _serve_forever(config: ChamberConfig) -> None:
    daemon = await start_daemon(config, default_backend(config))
    try:
        await asyncio.Event().wait()  # until Ctrl+C or the process is stopped
    finally:
        await daemon.close()
