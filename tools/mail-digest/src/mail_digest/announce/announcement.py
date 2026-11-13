"""One spoken message per run, built from the run's announcement candidates.

Candidates all come from the runner: the due and overdue items it picks from the
plans (deadlines/), sign-in reminders, skipped-mail notices, guard and failure alerts. Each has a
stable key, so an item already spoken on an earlier run is dropped here.
"""

from collections.abc import Container, Iterable
from dataclasses import dataclass


@dataclass(frozen=True)
class Announcement:
    """One thing to say once.

    key: stable id in the stored-key form (memory.state.KEY_PATTERN).
    sentence: one short spoken sentence, no links or markdown.
    """

    key: str
    sentence: str


def compose(
    candidates: Iterable[Announcement],
    announced: Container[str],
    max_items: int,
    more_hint: str = "Check the mail digest log.",
) -> tuple[str, tuple[str, ...]]:
    """The run's one spoken message and every key it covers.

    Drops candidates whose key was already announced (and repeats within the run),
    speaks the first max_items and sums up the rest in one sentence ending in
    more_hint (where the owner finds them). Only the
    spoken items' keys are returned, so a summed-up item can be spoken on a later
    run. Returns ("", ()) when nothing is new.
    """
    fresh = fresh_announcements(candidates, announced)
    if not fresh:
        return "", ()
    sentences = [c.sentence for c in fresh[:max_items]]
    extra = len(fresh) - max_items
    if extra > 0:
        sentences.append(f"Plus {extra} more. {more_hint}")
    return " ".join(sentences), tuple(c.key for c in fresh[:max_items])


def fresh_announcements(
    candidates: Iterable[Announcement], announced: Container[str]
) -> list[Announcement]:
    """The candidates not announced yet, in order, the first of each key only."""
    unique: dict[str, Announcement] = {}
    for candidate in candidates:
        if candidate.key not in announced:
            unique.setdefault(candidate.key, candidate)  # the first one with a key wins
    return list(unique.values())
