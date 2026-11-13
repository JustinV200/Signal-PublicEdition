"""Append to the event log under its lock: number the line, give it a ref, fold unchanged ones.

Under the lock each line takes the next seq from counters.json, and a key's first
line takes its kind's letter and that letter's next count. Later lines for the key
copy its ref, since compaction keeps only the last. A line whose digest matches
its key's current one isn't rewritten, so a producer re-logging the same thing
doesn't make it new again.
"""

import logging
from dataclasses import replace
from datetime import datetime

from signal_brief.log.compact import maybe_compact_locked
from signal_brief.log.counters import Counters, read_counters, write_counters
from signal_brief.log.entry import KIND_LETTERS, Entry, NewEntry, entry_digest
from signal_brief.log.read import find_entry, fold, read_log
from signal_brief.log.validate import validate_new_entry
from signal_brief.paths import BriefPaths
from signal_brief.store import BriefLogError, state_lock
from signal_brief.text import ERROR_QUOTE_CHARS

log = logging.getLogger(__name__)


def append_entry(paths: BriefPaths, new: NewEntry, now: datetime) -> Entry:
    """Validate `new` and log it.

    Args:
        paths: The state files.
        new: What to log.
        now: The time it's logged (aware).

    Returns:
        The entry as logged, or the key's current entry if nothing changed.

    Raises:
        ValueError: `new` breaks a rule (signal_brief.log.validate).
        BriefLogError: The lock timed out, or the log couldn't be written.
    """
    validate_new_entry(new)
    with state_lock(paths):
        return append_locked(paths, new, now)


def resolve_entry(paths: BriefPaths, key_or_ref: str, now: datetime) -> Entry:
    """Mark a key resolved (an open wait leaves the brief), by its ref or key.

    Raises:
        ValueError: No entry has that ref or key.
        BriefLogError: The lock timed out, or the log couldn't be written.
    """
    with state_lock(paths):
        entry = find_entry(list(fold(read_log(paths.events)).values()), key_or_ref)
        if entry is None:
            raise ValueError(f"no brief entry {key_or_ref[:ERROR_QUOTE_CHARS]!r}")
        return append_locked(paths, entry.content, now, resolved=True)


def append_locked(paths: BriefPaths, new: NewEntry, now: datetime, resolved: bool = False) -> Entry:
    """append_entry's work, for a caller already holding the lock (no validation).

    Raises:
        BriefLogError: The log or counters couldn't be read or written.
    """
    logged = read_log(paths.events)
    previous = fold(logged).get(new.key) if new.key else None
    digest = entry_digest(new, resolved)
    if previous is not None and previous.digest == digest:
        return previous
    counters = _caught_up(read_counters(paths), logged)
    counters.seq += 1
    content = new if new.key else replace(new, key=f"auto:{counters.seq}")
    ref = previous.ref if previous else _next_ref(counters, new.kind)
    entry = Entry(counters.seq, ref, now, content, resolved, digest)
    # Counters first: a failed line write then leaves a gap, never a reused seq.
    write_counters(paths, counters)
    _append_line(paths, entry.to_line())
    try:
        maybe_compact_locked(paths, counters, now)
    except BriefLogError as error:
        # The entry is already logged; compaction just runs again on a later append.
        log.warning("log compaction failed, retried on the next append: %s", error)
    return entry


def _next_ref(counters: Counters, kind: str) -> str:
    letter = KIND_LETTERS[kind]
    counters.refs[letter] = counters.refs.get(letter, 0) + 1
    return f"{letter}{counters.refs[letter]}"


def _caught_up(counters: Counters, logged: list[Entry]) -> Counters:
    """Counters never behind the log, in case counters.json was lost or hand-edited.

    Without this a lost file would restart the counts and hand out a ref that
    already names something.
    """
    for entry in logged:
        counters.seq = max(counters.seq, entry.seq)
        letter, count = entry.ref[:1], entry.ref[1:]
        if count.isdigit():
            counters.refs[letter] = max(counters.refs.get(letter, 0), int(count))
    return counters


def _append_line(paths: BriefPaths, line: str) -> None:
    try:
        with paths.events.open("a", encoding="utf-8", newline="\n") as log_file:
            log_file.write(f"{line}\n")
    except OSError as error:
        raise BriefLogError(f"can't append to {paths.events.name}: {error}") from error
