"""Notifier: posts notes to the voice hub in the background, never failing the caller.

A caller (a session's reader, a browser tool call) must not wait on the hub,
and a hub that isn't running is normal (the owner may not be using voice), so
delivery runs in its own task and every failure is logged and dropped. Each
delivery's outcome (a Delivery) is still there for a caller that wants it:
post returns the delivery's task, and deliver returns it directly. The
hub's token is read from its token file at each delivery (the hub writes a new
one when it restarts); no file means the hub isn't running.
"""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from signal_hub_notify.client import (
    HubDroppedError,
    HubNote,
    HubRejectedError,
    HubUnavailableError,
    send_to_hub,
)

logger = logging.getLogger(__name__)

# audiohub writes its token as ASCII (secrets.token_urlsafe).
TOKEN_ENCODING = "ascii"

# Same shape as client.send_to_hub, so tests can pass a fake.
SendToHub = Callable[[str, int, HubNote, str], Awaitable[str]]


class DeliveryStatus(Enum):
    """How a note's delivery ended."""

    SPOKEN = "spoken"  # the hub accepted it for speaking
    DROPPED = "dropped"  # the hub dropped it unspoken (the owner is asleep or away)
    NO_HUB = "no_hub"  # the hub isn't running (no token file, or nothing listening)
    FAILED = "failed"  # refused, unreadable reply, timeout or another socket error


@dataclass(frozen=True)
class Delivery:
    """The outcome of one delivery.

    Attributes:
        status: How it ended.
        reason: For DROPPED, the hub's reason (one of client.DROP_REASONS); else None.
    """

    status: DeliveryStatus
    reason: str | None = None


class Notifier:
    """Delivers notes to the hub at one address."""

    def __init__(
        self, host: str, port: int, token_file: Path, send: SendToHub = send_to_hub
    ) -> None:
        """Configure the notifier. Nothing is read or connected until a note is posted.

        Args:
            host: The hub's loopback address.
            port: The hub's kernel port.
            token_file: Where the hub publishes its kernel's token.
            send: Delivers one note; tests pass a fake.
        """
        self._host = host
        self._port = port
        self._token_file = token_file
        self._send = send
        self._pending: set[asyncio.Task[Delivery]] = set()

    def post(self, note: HubNote) -> asyncio.Task[Delivery]:
        """Start delivering a note and return at once. Must be called from the event loop.

        Args:
            note: The message for the owner.

        Returns:
            The delivery's task; awaiting it gives the Delivery (it never raises).
            Callers that don't care can ignore it.
        """
        task = asyncio.create_task(self.deliver(note), name=f"notify:{note.source}")
        # Keep a reference so the task isn't garbage-collected mid-flight.
        self._pending.add(task)
        task.add_done_callback(self._pending.discard)
        return task

    async def deliver(self, note: HubNote) -> Delivery:
        """Deliver a note now, logging (not raising) any failure.

        Args:
            note: The message for the owner.

        Returns:
            How the delivery ended. Never raises.
        """
        token = _read_token(self._token_file)
        try:
            if token is None:
                raise HubUnavailableError(f"no voice hub token at {self._token_file}")
            message_id = await self._send(self._host, self._port, note, token)
        except HubUnavailableError:
            logger.info("Voice hub not running; dropped %s note: %s", note.priority, note.text)
            return Delivery(DeliveryStatus.NO_HUB)
        except HubDroppedError as error:
            logger.info("Voice hub dropped a note from %s: %s", note.source, error.reason)
            return Delivery(DeliveryStatus.DROPPED, error.reason)
        except (HubRejectedError, TimeoutError, OSError) as error:
            logger.warning("Couldn't deliver note to the voice hub (%s): %s", error, note.text)
            return Delivery(DeliveryStatus.FAILED)
        logger.info("Voice hub queued note %s from %s", message_id, note.source)
        return Delivery(DeliveryStatus.SPOKEN)

    async def drain(self) -> None:
        """Wait for every posted note to finish delivering (used at shutdown and in tests)."""
        # Only unfinished tasks: a finished one stays in the set until its discard
        # callback runs, and gather() of finished tasks completes without yielding to
        # the loop, so waiting on those would spin forever and the callback never runs.
        while pending := [task for task in self._pending if not task.done()]:
            await asyncio.gather(*pending)


def _read_token(path: Path) -> str | None:
    """The hub's token, or None when the file is missing, unreadable or empty.

    A missing file is the normal "hub not running" case; anything else is
    logged, and also treated as the hub being unavailable.

    TODO: this mirrors claude_sessions.tokens.read_token (tools/sessions). This
    package must stay stdlib-only and can't import a tool, so it has its own
    copy. Move both to a shared token-file package under packages/ once one exists.
    """
    try:
        token = path.read_text(encoding=TOKEN_ENCODING).strip()
    except FileNotFoundError:
        return None
    except (OSError, UnicodeDecodeError) as error:
        logger.warning("Can't read the voice hub token file %s: %s", path, error)
        return None
    return token or None
