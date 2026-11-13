"""Public API of signal_console.server.security: the request guard, headers and page login."""

from signal_console.server.security.guards import LOGIN_PATH, add_security_headers, build_guard
from signal_console.server.security.sessions import (
    LOGIN_KEY_TTL_S,
    MAX_SESSIONS,
    SESSION_TOKEN_HEADER,
    SessionAuth,
)

__all__ = [
    "LOGIN_KEY_TTL_S",
    "LOGIN_PATH",
    "MAX_SESSIONS",
    "SESSION_TOKEN_HEADER",
    "SessionAuth",
    "add_security_headers",
    "build_guard",
]
