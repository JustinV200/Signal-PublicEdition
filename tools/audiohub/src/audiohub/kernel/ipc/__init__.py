"""Public API of audiohub.kernel.ipc: the hub's loopback notification server and client.

`KernelServer` runs inside the hub; `send_notification` is called from other
processes. Both speak newline-delimited JSON (see protocol.py).
`PresenceFiles` tells the server when to drop notifications. The token
helpers are shared with the phone bridge, which guards its page the same way.
`KernelServer` loads on first use: it pulls in the `Kernel` and its Sonnet
dispatcher, which a process that only sends notifications doesn't need.
"""

import importlib
from typing import TYPE_CHECKING, Any

from .auth_token import (
    create_token_file,
    read_token,
    remove_token_file,
    restrict_to_current_user,
    tokens_match,
)
from .client import (
    HubNotRunningError,
    NotificationDroppedError,
    NotificationRejectedError,
    send_notification,
)
from .presence import PresenceFiles
from .protocol import MAX_LINE_BYTES, ProtocolError

if TYPE_CHECKING:
    from .server import KernelServer


def __getattr__(name: str) -> Any:
    """Import `KernelServer` on first access (PEP 562)."""
    if name != "KernelServer":
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    return importlib.import_module(".server", __name__).KernelServer


__all__ = [
    "MAX_LINE_BYTES",
    "HubNotRunningError",
    "KernelServer",
    "NotificationDroppedError",
    "NotificationRejectedError",
    "PresenceFiles",
    "ProtocolError",
    "create_token_file",
    "read_token",
    "remove_token_file",
    "restrict_to_current_user",
    "send_notification",
    "tokens_match",
]
