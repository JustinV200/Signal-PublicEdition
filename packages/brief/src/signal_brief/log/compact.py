"""Compaction: past 512 KB, or weekly, keep each key's last line and drop old, seen closed keys.

Refs and seqs live on in the kept lines and in counters.json, so nothing a reader
holds (a ref, the bookmark) moves. An entry past the bookmark (one the owner hasn't
been briefed on) is never dropped, however old: briefs build up until the owner sees them.
"""

from datetime import datetime, timedelta

from signal_brief.log.bookmark import read_through
from signal_brief.log.counters import Counters, write_counters
from signal_brief.log.read import current_entries
from signal_brief.paths import BriefPaths
from signal_brief.store import BriefLogError, write_text_atomic

MAX_LOG_BYTES = 512 * 1024
COMPACT_EVERY = timedelta(days=7)
# A closed key (anything but an open wait) at or before the bookmark whose last line
# is older than this goes.
KEEP_CLOSED_FOR = timedelta(days=30)


def maybe_compact_locked(paths: BriefPaths, counters: Counters, now: datetime) -> bool:
    """Compact if the log is too big or a week has passed. Call under the log's lock.

    Args:
        paths: The state files.
        counters: The counters just written; their compacted_at is updated.
        now: The time of this append.

    Returns:
        True if it compacted.

    Raises:
        BriefLogError: The log couldn't be read or rewritten.
    """
    try:
        size = paths.events.stat().st_size
    except OSError as error:
        raise BriefLogError(f"can't stat {paths.events.name}: {error}") from error
    weekly = counters.compacted_at is None or now - counters.compacted_at >= COMPACT_EVERY
    if size <= MAX_LOG_BYTES and not weekly:
        return False
    through = read_through(paths)
    kept = [
        entry
        for entry in current_entries(paths)
        if entry.seq > through or not entry.is_closed or now - entry.at <= KEEP_CLOSED_FOR
    ]
    write_text_atomic(paths.events, "".join(f"{entry.to_line()}\n" for entry in kept))
    counters.compacted_at = now
    write_counters(paths, counters)
    return True
