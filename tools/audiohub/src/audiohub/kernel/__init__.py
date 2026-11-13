"""Public API of audiohub.kernel: every message bound for the user passes through here.

Producers `submit` messages to the `Kernel`; a Sonnet `Dispatcher` decides the
order and timing, passes text through verbatim and condenses only what is too
long to listen to. `KernelServer` / `send_notification` let other processes
submit messages over loopback TCP.

This package imports nothing from audiohub except `audiohub.config`, so it can
later be lifted into its own tool.

The names that need claude_agent_sdk (the dispatcher, the `Kernel` and its
server) load on first use, so `audiohub notify` and the MCP server, which
only send notifications, skip its ~0.6 s import.
"""

import importlib
from typing import TYPE_CHECKING, Any

from .inbox import Inbox
from .ipc import (
    HubNotRunningError,
    NotificationDroppedError,
    NotificationRejectedError,
    PresenceFiles,
    ProtocolError,
    create_token_file,
    read_token,
    remove_token_file,
    restrict_to_current_user,
    send_notification,
    tokens_match,
)
from .messages import (
    PRIORITIES,
    Decision,
    DeliveredRecord,
    OutboundMessage,
    Priority,
    create_message,
)

if TYPE_CHECKING:
    from .dispatch import DISPATCHER_PROMPT, Dispatcher, DispatcherBackend, fallback_policy
    from .facade import Kernel
    from .ipc import KernelServer

# Lazily loaded name -> the submodule (relative to this package) that defines it.
_LAZY = {
    "DISPATCHER_PROMPT": ".dispatch",
    "Dispatcher": ".dispatch",
    "DispatcherBackend": ".dispatch",
    "fallback_policy": ".dispatch",
    "Kernel": ".facade",
    "KernelServer": ".ipc.server",
}


def __getattr__(name: str) -> Any:
    """Import a heavy name on first access (PEP 562)."""
    if name not in _LAZY:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    return getattr(importlib.import_module(_LAZY[name], __name__), name)


__all__ = [
    "DISPATCHER_PROMPT",
    "PRIORITIES",
    "Decision",
    "DeliveredRecord",
    "Dispatcher",
    "DispatcherBackend",
    "HubNotRunningError",
    "Inbox",
    "Kernel",
    "KernelServer",
    "NotificationDroppedError",
    "NotificationRejectedError",
    "OutboundMessage",
    "PresenceFiles",
    "Priority",
    "ProtocolError",
    "create_message",
    "create_token_file",
    "fallback_policy",
    "read_token",
    "remove_token_file",
    "restrict_to_current_user",
    "send_notification",
    "tokens_match",
]
