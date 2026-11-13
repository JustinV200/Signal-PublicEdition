"""The MCP `notify` tool: hands a message for the user to a running voice hub.

The hub's kernel decides when to speak it. Delivery goes through
`audiohub.kernel.send_notification` (a blocking loopback TCP client), so the
call runs in a worker thread to keep the MCP event loop free. Every failure
becomes a plain-text result that says the message was not delivered, because
the calling model needs to know the user did not hear it. A note the hub
drops because the user is asleep or away says so ("dropped: the owner is asleep").
"""

import asyncio
import logging
from collections.abc import Callable

from audiohub.config import IpcSettings
from audiohub.kernel import (
    HubNotRunningError,
    NotificationDroppedError,
    NotificationRejectedError,
    Priority,
    ProtocolError,
    send_notification,
)

logger = logging.getLogger(__name__)

DEFAULT_SOURCE = "claude-code"
DEFAULT_PRIORITY: Priority = "normal"

# Endings for a failed delivery's result text, after the reason.
NOT_DELIVERED = "the message was not delivered and the user did not hear it"
MAYBE_NOT_DELIVERED = "the message may not have been delivered"

HUB_NOT_RUNNING_REASON = "The audiohub voice hub isn't running"
# Replaces the error's details, which say how to start the hub: a model reading
# them would try to launch it itself instead of telling the user.
HUB_NOT_RUNNING_ADVICE = (
    "Tell the user the voice hub isn't running. Don't try to start it yourself."
)

# Notes from agents are dropped, not queued, while the user is asleep or away.
DROPPED_ADVICE = "Don't resend it; the user won't hear notes until they're back."

# Same shape as `kernel.send_notification(host, port, source, text, priority)`,
# so tests can pass a fake in its place.
SendNotification = Callable[[str, int, str, str, Priority], str]


class NotifyTool:
    """Backs the `notify` tool with the hub address from settings.

    Args:
        ipc: Where the hub's kernel server listens.
        send: The delivery function (default: the real kernel client).
    """

    def __init__(self, ipc: IpcSettings, send: SendNotification = send_notification) -> None:
        self._ipc = ipc
        self._send = send

    async def notify(
        self, text: str, priority: Priority = DEFAULT_PRIORITY, source: str = DEFAULT_SOURCE
    ) -> str:
        """Send `text` to the hub to be spoken to the user.

        Args:
            text: What the user should hear.
            priority: "urgent", "high", "normal" or "low".
            source: Short name of the sender, e.g. "build-agent".

        Returns:
            A confirmation with the kernel's message id, or a sentence saying
            the message was not delivered and why. Never raises for delivery
            failures.
        """
        try:
            message_id = await asyncio.to_thread(
                self._send, self._ipc.host, self._ipc.port, source, text, priority
            )
        except HubNotRunningError as error:
            logger.warning("notify: %s (%s)", HUB_NOT_RUNNING_REASON, error)
            return f"{HUB_NOT_RUNNING_REASON}, so {NOT_DELIVERED}. {HUB_NOT_RUNNING_ADVICE}"
        except NotificationDroppedError as error:
            logger.info("notify: %s", error)
            return f"Not spoken ({error}). {DROPPED_ADVICE}"
        except (ProtocolError, NotificationRejectedError) as error:
            return _not_delivered("The message was rejected", error)
        except TimeoutError as error:
            # The request was already sent, so the hub may still speak it.
            reason = "The voice hub didn't confirm the message in time"
            return _not_delivered(reason, error, MAYBE_NOT_DELIVERED)
        except OSError as error:
            return _not_delivered("The connection to the voice hub failed", error)
        return f"Sent to the voice hub as message {message_id}; it will be spoken to the user."


def _not_delivered(reason: str, error: Exception, outcome: str = NOT_DELIVERED) -> str:
    """Log a failed delivery and build the tool result that explains it."""
    logger.warning("notify: %s (%s)", reason, error)
    detail = str(error) or type(error).__name__
    return f"{reason}, so {outcome}. Details: {detail}"
