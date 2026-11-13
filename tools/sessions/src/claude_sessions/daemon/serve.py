"""serve: runs the sessions daemon until Ctrl+C or a shutdown request.

Wires the real collaborators (SDK client, Windows dialog approver, voice-hub
notifier, transcript lookup, sessions.json store) into a SessionManager and
serves it over IPC. The port is bound before sessions.json is loaded, and a
fresh token is written only after that. On the way out every live session is
stopped before the port is released. A kill-on-close job object covers a
hard crash, so no CLI process outlives the daemon either way.
"""

import asyncio
import logging
import time

from signal_hub_notify import Notifier

from claude_sessions.approvals import Approver, DialogApprover
from claude_sessions.config import Settings, daemon_token_file, sessions_file
from claude_sessions.daemon.job_object import kill_children_with_daemon
from claude_sessions.daemon.manager import ManagerDeps, SessionManager
from claude_sessions.daemon.server import DaemonServer, ListenSpec
from claude_sessions.daemon.session import SessionStore
from claude_sessions.repos import find_transcript_cwd
from claude_sessions.sdk import ClientFactory, create_sdk_client

logger = logging.getLogger(__name__)


async def serve(
    settings: Settings,
    approver: Approver | None = None,
    client_factory: ClientFactory = create_sdk_client,
) -> None:
    """Serve until a shutdown request arrives or the task is cancelled.

    Args:
        settings: Ports, state folder and approval timeout.
        approver: Decides tool calls; default DialogApprover.
        client_factory: Builds SDK clients; default the real ClaudeSDKClient.

    Raises:
        OSError: The daemon port is already in use, or the token can't be written.
    """
    kill_children_with_daemon()
    notifier = Notifier(settings.hub_host, settings.hub_port, settings.hub_token_file)
    deps = ManagerDeps(
        store=SessionStore(sessions_file(settings.state_dir)),
        client_factory=client_factory,
        approver=approver or DialogApprover(settings.approval_timeout_s),
        notifier=notifier,
        find_transcript_cwd=find_transcript_cwd,
        clock=time.time,
        repo_roots=settings.repo_roots,
    )
    manager = SessionManager(deps)
    shutdown_requested = asyncio.Event()
    token_file = daemon_token_file(settings.state_dir, settings.daemon_port)
    listen = ListenSpec(settings.daemon_host, settings.daemon_port, token_file)
    server = DaemonServer(manager, listen, shutdown_requested.set)
    # Port first: a rival daemon that can't bind stops here, before touching sessions.json.
    await server.bind()
    try:
        manager.load()
        # Publishes the token, then accepts connections.
        await server.start()
        await shutdown_requested.wait()
        logger.info("Shutdown requested")
    finally:
        # Stop sessions while still holding the port, so a successor daemon can't
        # load sessions.json before these last saves land.
        await manager.stop_all()
        await server.close()
        await notifier.drain()
        logger.info("Sessions daemon stopped")
