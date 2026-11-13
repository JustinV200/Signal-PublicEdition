"""dispatch: runs one validated IPC request against the SessionManager and returns its result.

The protocol (ipc.protocol) has already checked op names, argument names,
types and sizes, so this only maps ops to manager calls.
"""

import os
from collections.abc import Callable
from typing import Any

from claude_sessions import __version__
from claude_sessions.approvals import DEFAULT_PERMISSION_MODE
from claude_sessions.daemon.manager import DEFAULT_LAST_N, SessionManager
from claude_sessions.ipc import Request


async def dispatch(
    manager: SessionManager, request: Request, on_shutdown: Callable[[], None]
) -> Any:
    """Run one request.

    Args:
        manager: The daemon's sessions.
        request: A request that passed ipc.parse_request.
        on_shutdown: Called for the shutdown op, after which the daemon exits.

    Returns:
        JSON-ready result data.

    Raises:
        SessionError, PermissionModeError: The manager refused the operation.
    """
    args = request.args
    match request.op:
        case "ping":
            return {"pid": os.getpid(), "version": __version__}
        case "list":
            return manager.list()
        case "start":
            mode = args.get("permission_mode", DEFAULT_PERMISSION_MODE)
            return await manager.start(args["repo"], args["prompt"], args.get("model"), mode)
        case "send":
            return await manager.send(args["id"], args["prompt"])
        case "status":
            return manager.status(args["id"], args.get("last_n", DEFAULT_LAST_N))
        case "resume":
            return await manager.resume(args["session"], args["prompt"])
        case "stop":
            return await manager.stop(args["id"])
        case "shutdown":
            on_shutdown()
            return {"stopping": True}
    # Unreachable while OPS and this match stay in step; fail loudly if they don't.
    raise NotImplementedError(f"op {request.op!r} has no handler")
