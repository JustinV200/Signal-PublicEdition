"""Public API of claude_sessions.daemon: the process holding live managed Claude Code sessions."""

from claude_sessions.daemon.manager import ManagerDeps, SessionManager
from claude_sessions.daemon.serve import serve
from claude_sessions.daemon.server import DaemonServer, ListenSpec
from claude_sessions.daemon.session import (
    ManagedSession,
    SessionError,
    SessionRecord,
    SessionState,
    SessionStore,
)

__all__ = [
    "DaemonServer",
    "ListenSpec",
    "ManagedSession",
    "ManagerDeps",
    "SessionError",
    "SessionManager",
    "SessionRecord",
    "SessionState",
    "SessionStore",
    "serve",
]
