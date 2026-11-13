"""Public API of claude_sessions.ipc: the daemon's wire protocol, its client, and auto-start."""

from claude_sessions.ipc.client import (
    DaemonEndpoint,
    DaemonNotRunningError,
    DaemonRequestError,
    call_daemon,
)
from claude_sessions.ipc.launcher import (
    DaemonStartError,
    call_running_daemon,
    daemon_endpoint,
    ensure_daemon,
    is_daemon_running,
    spawn_daemon,
)
from claude_sessions.ipc.protocol import (
    LINE_END,
    MAX_LINE_BYTES,
    MAX_PROMPT_CHARS,
    MAX_STATUS_TEXTS,
    OPS,
    AuthError,
    ProtocolError,
    Request,
    encode_error,
    encode_ok,
    parse_request,
)

__all__ = [
    "LINE_END",
    "MAX_LINE_BYTES",
    "MAX_PROMPT_CHARS",
    "MAX_STATUS_TEXTS",
    "OPS",
    "AuthError",
    "DaemonEndpoint",
    "DaemonNotRunningError",
    "DaemonRequestError",
    "DaemonStartError",
    "ProtocolError",
    "Request",
    "call_daemon",
    "call_running_daemon",
    "daemon_endpoint",
    "encode_error",
    "encode_ok",
    "ensure_daemon",
    "is_daemon_running",
    "parse_request",
    "spawn_daemon",
]
