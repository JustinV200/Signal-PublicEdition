"""Public API of claude_sessions.daemon.session: one managed session, its record, store and views.

The rest of the daemon (manager, server) imports from here only.
"""

from claude_sessions.daemon.session.errors import SessionError
from claude_sessions.daemon.session.managed import ManagedSession, SessionDeps
from claude_sessions.daemon.session.record import SessionRecord, SessionState
from claude_sessions.daemon.session.store import SessionStore
from claude_sessions.daemon.session.views import session_status, session_summary

__all__ = [
    "ManagedSession",
    "SessionDeps",
    "SessionError",
    "SessionRecord",
    "SessionState",
    "SessionStore",
    "session_status",
    "session_summary",
]
