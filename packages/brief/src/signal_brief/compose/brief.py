"""compose: the brief as data, deterministic and model-free.

A brief covers every entry past the bookmark plus every open wait, in section
order (waiting, decision, heads_up, new, done) and, within a section, by priority
then newest. Its id, b-<hash>, hashes the kind and the covered refs and seqs, so
it changes whenever an append or ack changes what it covers.

Phase 1 has only the general brief; the morning one (greeting, weather, today)
comes with phase 3's morning composer.
"""

import hashlib
import json
from dataclasses import dataclass

from signal_brief.log import KINDS, PRIORITIES, Entry, current_entries, read_through
from signal_brief.paths import BriefPaths

BRIEF_KINDS = ("general",)
BRIEF_ID_HASH_CHARS = 10
SECTION_LABELS: dict[str, str] = {
    "waiting": "Waiting on you",
    "decision": "Decided for you",
    "heads_up": "Heads up",
    "new": "New",
    "done": "Done",
}


@dataclass(frozen=True)
class Brief:
    """One composed brief.

    Attributes:
        id: b-<hash> of the kind and covered entries.
        kind: One of BRIEF_KINDS.
        through: The bookmark when it was composed.
        items: The covered entries, best-ranked first; renders cut from the end.
    """

    id: str
    kind: str
    through: int
    items: tuple[Entry, ...]

    @property
    def unseen(self) -> int:
        """Items past the bookmark (open waits the owner's already seen don't count)."""
        return sum(1 for item in self.items if item.seq > self.through)


def compose(paths: BriefPaths, kind: str = "general") -> Brief:
    """Compose the brief from the log and the bookmark.

    Raises:
        ValueError: An unknown kind.
        BriefLogError: The log or bookmark couldn't be read.
    """
    if kind not in BRIEF_KINDS:
        raise ValueError(f"kind must be one of {', '.join(BRIEF_KINDS)}")
    through = read_through(paths)
    covered = [
        entry
        for entry in current_entries(paths)
        if not entry.resolved and (entry.seq > through or entry.content.kind == "waiting")
    ]
    items = tuple(sorted(covered, key=_rank))
    return Brief(_brief_id(kind, items), kind, through, items)


def _rank(entry: Entry) -> tuple[int, int, int]:
    """Section, then priority, then newest. (Soonest due joins with phase 4's due items.)"""
    return KINDS.index(entry.content.kind), PRIORITIES.index(entry.content.priority), -entry.seq


def _brief_id(kind: str, items: tuple[Entry, ...]) -> str:
    covered = json.dumps([kind, [[item.ref, item.seq] for item in items]]).encode()
    return f"b-{hashlib.sha256(covered).hexdigest()[:BRIEF_ID_HASH_CHARS]}"
