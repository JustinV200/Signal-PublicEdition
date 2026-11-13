"""Public API of signal_hub_notify: hand voice notes to the audiohub hub's kernel.

send_to_hub delivers one note and raises on failure; Notifier posts notes in
the background and only logs failures, so callers never wait on the hub, and
reports each outcome as a Delivery for callers that want it.
"""

from signal_hub_notify.client import (
    DROP_REASONS,
    MAX_SOURCE_CHARS,
    HubDroppedError,
    HubNote,
    HubRejectedError,
    HubUnavailableError,
    Priority,
    send_to_hub,
)
from signal_hub_notify.notifier import Delivery, DeliveryStatus, Notifier, SendToHub

__all__ = [
    "DROP_REASONS",
    "MAX_SOURCE_CHARS",
    "Delivery",
    "DeliveryStatus",
    "HubDroppedError",
    "HubNote",
    "HubRejectedError",
    "HubUnavailableError",
    "Notifier",
    "Priority",
    "SendToHub",
    "send_to_hub",
]
