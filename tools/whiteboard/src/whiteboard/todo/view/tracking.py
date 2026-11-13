"""track: what a sync changed, compared with the last one.

Two things need memory between syncs (kept in .state/todo.json by TodoStore):
- `done_since`: the first day a sync saw each item done. Done items stay on the
  board, struck through, for the rest of that day; from the next day they're hidden.
- `open_ids`: the items that were open at the last sync. An item that was open
  then and is done now is "newly done": the page plays the cross-out animation.
An item seen done for the first time (never seen open) counts as done today, so it
shows struck through until tomorrow but isn't animated. An unticked item forgets
its done day, and items no longer in the plans are dropped.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date

from whiteboard.todo.source import PlanEntry


@dataclass(frozen=True)
class DoneTracking:
    """The memory one sync leaves for the next (see the module docstring)."""

    done_since: Mapping[str, date] = field(default_factory=dict)
    open_ids: frozenset[str] = frozenset()


@dataclass(frozen=True)
class TrackResult:
    """The outcome of one sync.

    Attributes:
        tracking: The memory to store for the next sync.
        done_ids: Items with at least one ticked line.
        hidden_ids: Done items whose done day is before today.
        newly_done: Items open at the last sync and done now (and still shown).
    """

    tracking: DoneTracking
    done_ids: frozenset[str]
    hidden_ids: frozenset[str]
    newly_done: frozenset[str]


def track(entries: Sequence[PlanEntry], previous: DoneTracking, today: date) -> TrackResult:
    """Compare the fresh parse with the last sync's memory.

    Args:
        entries: Every parsed todo line (several lines may share an id; any tick counts).
        previous: What the last sync stored.
        today: The board's today.
    """
    all_ids = {entry.id for entry in entries}
    done_ids = frozenset(entry.id for entry in entries if entry.is_done)
    done_since = {item: previous.done_since.get(item, today) for item in done_ids}
    hidden_ids = frozenset(item for item, since in done_since.items() if since < today)
    newly_done = (done_ids - hidden_ids) & previous.open_ids
    return TrackResult(
        tracking=DoneTracking(done_since, frozenset(all_ids - done_ids)),
        done_ids=done_ids,
        hidden_ids=hidden_ids,
        newly_done=frozenset(newly_done),
    )
