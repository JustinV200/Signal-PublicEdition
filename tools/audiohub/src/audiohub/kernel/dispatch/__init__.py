"""Public API of audiohub.kernel.dispatch: the Sonnet dispatcher and its parts.

The `Dispatcher` asks a backend (a persistent Sonnet session by default) to
decide on pending messages, validates the JSON it returns, enforces the
kernel's fixed rules on it (safeguards.py), and falls back to a deterministic
policy whenever the reply can't be used.
"""

from .backend import BackendClosedError, DispatcherBackend, SonnetBackend
from .decisions import DecisionError, parse_decisions
from .dispatcher import Dispatcher
from .fallback import fallback_policy
from .prompt import DISPATCHER_PROMPT, DecisionRequest, render_request
from .sdk_session import BackendError

__all__ = [
    "DISPATCHER_PROMPT",
    "BackendClosedError",
    "BackendError",
    "DecisionError",
    "DecisionRequest",
    "Dispatcher",
    "DispatcherBackend",
    "SonnetBackend",
    "fallback_policy",
    "parse_decisions",
    "render_request",
]
