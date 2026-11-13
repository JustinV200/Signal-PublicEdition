"""One brief entry as a producer hands it in (NewEntry) and as logged (Entry).

`kind` picks the brief section, in this order: waiting (until resolved), decision
(needs an undo), heads_up (failures and alerts), new (school and email), done.
Each kind has a ref letter; a key's first line gets that letter and the letter's
next count (like D7), which every later line for the key keeps.
"""

import hashlib
import json
from dataclasses import asdict, dataclass, fields
from datetime import datetime
from typing import Any

from signal_brief.times import from_iso, to_iso

# Section order, and each kind's ref letter ("F" for done, so "D" stays decision).
KIND_LETTERS: dict[str, str] = {
    "waiting": "W",
    "decision": "D",
    "heads_up": "H",
    "new": "N",
    "done": "F",
}
KINDS: tuple[str, ...] = tuple(KIND_LETTERS)
# Highest first; ranking sorts by this index.
PRIORITIES: tuple[str, ...] = ("urgent", "high", "normal", "low")
DIGEST_CHARS = 16

# An undo action: the tool to call and its arguments, e.g.
# {"tool": "Bash", "args": {"command": "git revert 1a2b3c4"}}.
UndoAction = dict[str, Any]


@dataclass(frozen=True)
class NewEntry:
    """What a producer logs. Checked by validate_new_entry before it's written.

    Attributes:
        kind: One of KINDS.
        title: One line, at most 140 characters.
        key: Folds lines for one thing (last wins); "" means a new auto:<seq> key.
        detail: More text, at most 600 characters, newlines allowed.
        undo: For a decision, the action that reverses it; never on untrusted entries.
        priority: One of PRIORITIES.
        untrusted: The text came from outside (mail, invites, plan lines).
        source: Who logged it ("session", "managed", "sleepmode"...).
    """

    kind: str
    title: str
    key: str = ""
    detail: str = ""
    undo: UndoAction | None = None
    priority: str = "normal"
    untrusted: bool = False
    source: str = "session"


_CONTENT_FIELDS = tuple(field.name for field in fields(NewEntry))


@dataclass(frozen=True)
class Entry:
    """One line of the log: its content (key filled in), seq, permanent ref and digest."""

    seq: int
    ref: str
    at: datetime
    content: NewEntry
    resolved: bool
    digest: str

    @property
    def key(self) -> str:
        """The key the log folds this line under."""
        return self.content.key

    @property
    def is_closed(self) -> bool:
        """Only an unresolved wait stays open; everything else can age out of the log."""
        return self.resolved or self.content.kind != "waiting"

    def to_line(self) -> str:
        """The entry as one JSON line (no newline)."""
        head = {"seq": self.seq, "ref": self.ref, "at": to_iso(self.at)}
        tail = {"resolved": self.resolved, "digest": self.digest}
        return json.dumps(head | asdict(self.content) | tail, ensure_ascii=False)


def entry_digest(content: NewEntry, resolved: bool) -> str:
    """A hash of everything a reader sees, so an unchanged re-log isn't rewritten."""
    encoded = json.dumps([asdict(content), resolved], sort_keys=True).encode()
    return hashlib.sha256(encoded).hexdigest()[:DIGEST_CHARS]


def entry_from_payload(payload: object) -> Entry | None:
    """An Entry from one parsed log line, or None if it isn't a well-formed entry."""
    if not isinstance(payload, dict):
        return None
    at = from_iso(payload.get("at"))
    try:
        content = NewEntry(**{name: payload[name] for name in _CONTENT_FIELDS})
        seq, ref = int(payload["seq"]), str(payload["ref"])
        resolved, digest = bool(payload["resolved"]), str(payload["digest"])
        # Inside the try: a hand-edited list kind would raise TypeError here.
        if at is None or content.kind not in KIND_LETTERS or content.priority not in PRIORITIES:
            return None
    except (KeyError, TypeError, ValueError):
        return None
    return Entry(seq, ref, at, content, resolved, digest)
