"""Tail the hub's log (when `console hub start` started it) for its phase and `voice` events.

Lines already in the log when the server starts only set the phase; lines
written later become `voice` events. A "heard" line is held until the next
line: if that says "ignored" (no wake phrase) the speech is dropped, so
ambient talk never reaches the feed or history.jsonl. The hub writes both
lines at once, so a held line still alone a round later is published. A
repeat of the same hub error within ERROR_REPEAT_S is dropped, so a burst
shows once.
"""

import math
import time
from pathlib import Path
from typing import Any

from signal_console.hub import read_hub_record
from signal_console.paths import HUB_LOG_FILE
from signal_console.server.events import EventHub, new_event_id, now_iso
from signal_console.status import LogTail, parse_hub_line

ERROR_REPEAT_S = 30.0
IGNORED_KIND = "ignored"
HEARD_KIND = "heard"
ERROR_PREFIX = "error: "


class HubFeed:
    """The console hub's phase, read off its log; publishes what it hears and says."""

    def __init__(self, events: EventHub, state_dir: Path) -> None:
        """Set up; nothing is read until read()."""
        self._events = events
        self._state_dir = state_dir
        self._tail = LogTail(state_dir / HUB_LOG_FILE)
        self._hub_record = read_hub_record(state_dir)
        self._is_first_read = True
        self.phase: str | None = None
        # A "heard" event waiting to see whether the next line ignores it.
        self._held: dict[str, Any] | None = None
        self._last_error: tuple[str, float] = ("", -math.inf)

    def read(self) -> None:
        """Read the log's new lines, updating the phase and publishing feed events."""
        record = read_hub_record(self._state_dir)
        if record != self._hub_record:
            # A different hub (or none): its log starts over from the top.
            self._hub_record, self.phase, self._held = record, None, None
            self._tail.reset()
        # Without a record the log belongs to a stopped hub; re-reading it would repeat it.
        lines = self._tail.read_new_lines() if record is not None else []
        # Lines already there when the server started only set the phase.
        is_replay, self._is_first_read = self._is_first_read, False
        held, is_new = self._held, False
        for line in lines:
            parsed = parse_hub_line(line)
            if parsed is None:
                continue
            if parsed.kind == IGNORED_KIND:
                held = None  # The speech just heard had no wake phrase: drop it.
                continue
            self._publish(held)
            held = None
            self.phase = parsed.phase or self.phase
            if parsed.kind is None or is_replay:
                continue
            event = {"id": new_event_id(), "kind": parsed.kind, "text": parsed.text}
            if parsed.kind == HEARD_KIND:
                held, is_new = event, True
            else:
                self._publish(event)
        if held is not None and not is_new:
            self._publish(held)  # Held since last round with nothing after it: it stands.
            held = None
        self._held = held

    def _publish(self, event: dict[str, Any] | None) -> None:
        if event is None or self._is_repeat_error(event["text"]):
            return
        self._events.publish("voice", event | {"at": now_iso()})

    def _is_repeat_error(self, text: str) -> bool:
        if not text.startswith(ERROR_PREFIX):
            return False
        now = time.monotonic()
        last_text, last_at = self._last_error
        self._last_error = (text, now)
        return text == last_text and now - last_at < ERROR_REPEAT_S
