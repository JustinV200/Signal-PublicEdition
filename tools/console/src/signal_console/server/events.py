"""The console's event feed: fan events out to SSE listeners and keep recent history on disk.

`message`, `delivery`, `voice` and `note` events are kept (the last
HISTORY_LIMIT) in .state/history.jsonl and replayed to each new listener, so a
restart or a reconnect keeps the conversation and each message's delivery
status. `state` is live only (a new listener gets a fresh snapshot instead).
Event ids are unique across all event types, made once and stored, so replays
repeat them and clients dedupe by id.

The folder must exist (serve() makes and locks it at start); a write that
fails is logged, and only the replay after a restart loses that event.
"""

import asyncio
import json
import logging
import os
import uuid
from collections import deque
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

HISTORY_LIMIT = 200
HISTORY_EVENTS = frozenset({"message", "delivery", "voice", "note"})
# Rewrite the file down to HISTORY_LIMIT lines once it reaches this many.
COMPACT_AT_LINES = 2 * HISTORY_LIMIT
# A listener this far behind is dropped (its stream ends) rather than buffered forever.
LISTENER_QUEUE_SIZE = 1000

Event = tuple[str, dict[str, Any]]
# Put on a queue to end that listener's stream (server shutdown or overflow).
END_OF_STREAM: Event = ("", {})

log = logging.getLogger(__name__)


def new_event_id() -> str:
    """A fresh, unique event id."""
    return uuid.uuid4().hex


def now_iso() -> str:
    """The current UTC time for an event's `at`."""
    return datetime.now(UTC).isoformat(timespec="milliseconds")


class EventHub:
    """Publishes events to every listener and keeps the replayable history."""

    def __init__(self, history_path: Path) -> None:
        """Load the history saved by earlier runs from `history_path` (may not exist)."""
        self._path = history_path
        self._history: deque[Event] = deque(maxlen=HISTORY_LIMIT)
        self._listeners: set[asyncio.Queue[Event]] = set()
        self._lines_in_file = self._load()

    @property
    def listener_count(self) -> int:
        """How many SSE streams are open."""
        return len(self._listeners)

    def history(self) -> list[Event]:
        """The kept events (HISTORY_EVENTS), oldest first."""
        return list(self._history)

    def subscribe(self) -> asyncio.Queue[Event]:
        """Start receiving events; END_OF_STREAM on the queue means stop."""
        queue: asyncio.Queue[Event] = asyncio.Queue(LISTENER_QUEUE_SIZE)
        self._listeners.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue[Event]) -> None:
        """Stop sending to a listener."""
        self._listeners.discard(queue)

    def publish(self, name: str, data: dict[str, Any]) -> None:
        """Send an event to all listeners, keeping it if it's one of HISTORY_EVENTS."""
        if name in HISTORY_EVENTS:
            self._keep((name, data))
        for queue in list(self._listeners):
            try:
                queue.put_nowait((name, data))
            except asyncio.QueueFull:
                log.warning("dropping an SSE listener that stopped reading")
                self._end(queue)

    def close(self) -> None:
        """End every listener's stream (server shutdown)."""
        for queue in list(self._listeners):
            self._end(queue)

    def _end(self, queue: asyncio.Queue[Event]) -> None:
        self._listeners.discard(queue)
        while not queue.empty():
            queue.get_nowait()
        queue.put_nowait(END_OF_STREAM)

    def _keep(self, event: Event) -> None:
        self._history.append(event)
        try:
            if self._lines_in_file + 1 >= COMPACT_AT_LINES:
                self._rewrite()
            else:
                with self._path.open("a", encoding="utf-8") as history_file:
                    history_file.write(_encode(event))
                self._lines_in_file += 1
        except OSError as error:
            # The live feed still works; only the replay after a restart loses it.
            log.warning("couldn't save console history to %s: %s", self._path, error)

    def _rewrite(self) -> None:
        temp_path = self._path.with_suffix(".tmp")
        temp_path.write_text("".join(_encode(event) for event in self._history), encoding="utf-8")
        os.replace(temp_path, self._path)
        self._lines_in_file = len(self._history)

    def _load(self) -> int:
        try:
            lines = self._path.read_text(encoding="utf-8").splitlines()
        except FileNotFoundError:
            return 0
        except OSError as error:
            log.warning("couldn't read console history %s: %s", self._path, error)
            return 0
        events = [_decode(line) for line in lines[-HISTORY_LIMIT:]]
        self._history.extend(event for event in events if event is not None)
        if None in events:
            log.warning("skipped %d unreadable lines in %s", events.count(None), self._path)
        return len(lines)


def _encode(event: Event) -> str:
    return json.dumps({"event": event[0], "data": event[1]}) + "\n"


def _decode(line: str) -> Event | None:
    try:
        record = json.loads(line)
    except ValueError:
        return None
    if not isinstance(record, dict) or record.get("event") not in HISTORY_EVENTS:
        return None
    data = record.get("data")
    return (record["event"], data) if isinstance(data, dict) else None
