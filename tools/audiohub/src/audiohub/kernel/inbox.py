"""The kernel's inbox: messages waiting to be spoken plus a short delivered history.

The history lets the dispatcher spot repeats of something the user already
heard. The inbox is not thread-safe; the `Kernel` facade only touches it from
its event loop and funnels cross-thread submissions through its own lock.
"""

from collections import deque

from .messages import DeliveredRecord, OutboundMessage

DEFAULT_HISTORY_LIMIT = 20


class Inbox:
    """Pending messages in arrival order, plus a bounded history of delivered ones."""

    def __init__(self, history_limit: int = DEFAULT_HISTORY_LIMIT) -> None:
        """Create an empty inbox.

        Args:
            history_limit: How many delivered messages to remember (oldest go first).

        Raises:
            ValueError: If `history_limit` is less than 1.
        """
        if history_limit < 1:
            raise ValueError("history_limit must be at least 1")
        # dicts keep insertion order, so iteration is FIFO by arrival.
        self._pending: dict[str, OutboundMessage] = {}
        self._history: deque[DeliveredRecord] = deque(maxlen=history_limit)

    def __len__(self) -> int:
        """Return the number of pending messages."""
        return len(self._pending)

    def add(self, message: OutboundMessage) -> None:
        """Queue a message as pending.

        Raises:
            ValueError: If a message with the same id is already pending.
        """
        if message.id in self._pending:
            raise ValueError(f"message id {message.id!r} is already pending")
        self._pending[message.id] = message

    def get(self, message_id: str) -> OutboundMessage | None:
        """Return the pending message with this id, or None."""
        return self._pending.get(message_id)

    def pending(self) -> list[OutboundMessage]:
        """Return the pending messages, oldest arrival first."""
        return list(self._pending.values())

    def mark_delivered(self, message_id: str, spoken_text: str) -> DeliveredRecord:
        """Move a pending message into the delivered history.

        Args:
            message_id: Id of a pending message.
            spoken_text: The words that will be spoken (original or condensed).

        Returns:
            The new history record.

        Raises:
            KeyError: If no pending message has this id.
        """
        record = DeliveredRecord(message=self._pending.pop(message_id), spoken_text=spoken_text)
        self._history.append(record)
        return record

    def discard(self, message_id: str) -> OutboundMessage:
        """Remove a pending message without delivering it (a dropped duplicate).

        Raises:
            KeyError: If no pending message has this id.
        """
        return self._pending.pop(message_id)

    def requeue(self, messages: list[OutboundMessage]) -> None:
        """Put delivered messages back in front of the pending ones, history records removed.

        Args:
            messages: Messages that were delivered but never heard, in the
                order they should come back.
        """
        ids = {message.id for message in messages}
        kept = [record for record in self._history if record.message.id not in ids]
        self._history = deque(kept, maxlen=self._history.maxlen)
        self._pending = {m.id: m for m in messages} | self._pending

    def take_pending(self) -> list[OutboundMessage]:
        """Remove and return every pending message, oldest arrival first."""
        taken = list(self._pending.values())
        self._pending.clear()
        return taken

    def recent_delivered(self) -> list[DeliveredRecord]:
        """Return the delivered history, oldest first."""
        return list(self._history)
