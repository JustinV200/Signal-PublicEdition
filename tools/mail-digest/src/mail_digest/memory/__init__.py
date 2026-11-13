"""mail_digest.memory: what the runner remembers between runs, and the one-run-at-a-time lock."""

from mail_digest.memory.lock import LockHeldError, is_locked, run_lock
from mail_digest.memory.state import (
    DigestState,
    KeyRetention,
    Lookback,
    Pending,
    Window,
    advance_windows,
    is_valid_key,
    load_state,
    record_failure,
    remember_announced,
    save_state,
    search_windows,
)

__all__ = [
    "DigestState",
    "KeyRetention",
    "LockHeldError",
    "Lookback",
    "Pending",
    "Window",
    "advance_windows",
    "is_locked",
    "is_valid_key",
    "load_state",
    "record_failure",
    "remember_announced",
    "run_lock",
    "save_state",
    "search_windows",
]
