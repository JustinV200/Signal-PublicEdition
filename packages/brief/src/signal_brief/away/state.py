"""Away mode: away.json's flag, end and note, and away_status's view of it.

away_status reports "asleep" while sleepmode's is_asleep is set, "away" while away
mode's end is ahead, else "here". Away mode set without an end lasts 3 days from
the last time it was set, then ends by itself with a heads_up like "Away mode ended
after 3 days, 14 items held". Setting it again while it's on (a new note, say) keeps
an end the owner gave. Either way its end, like away_off ("I'm back"), marks a full
brief due.
"""

import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from signal_brief.log import NewEntry, append_locked, current_entries, read_counters
from signal_brief.paths import BriefPaths
from signal_brief.presence import mark_due_locked
from signal_brief.store import (
    read_bytes_retrying,
    read_json_object,
    state_lock,
    write_json_atomic,
)
from signal_brief.text import check_text
from signal_brief.times import from_iso, to_iso

AWAY_WITHOUT_END = timedelta(days=3)
MAX_NOTE_CHARS = 140


@dataclass(frozen=True)
class AwayStatus:
    """Where the owner is, as far as the brief knows.

    Attributes:
        state: "asleep" (sleepmode), "away" (away mode) or "here".
        ends_at: When away mode ends (the end the owner gave, or 3 days after it was last set).
        note: the owner's note for away mode ("" if none).
        since_seq: The log's seq when away began; later entries were held for the owner.
        end_given: the owner gave the end (else it's the 3-day default).
    """

    state: str
    ends_at: datetime | None = None
    note: str = ""
    since_seq: int = 0
    end_given: bool = False

    @property
    def is_away(self) -> bool:
        """True while asleep or away: sessions follow the away rules."""
        return self.state != "here"


def away_on(paths: BriefPaths, now: datetime, until: datetime | None, note: str = "") -> AwayStatus:
    """Turn away mode on, or change its end and note while it's on.

    Args:
        paths: The state files.
        now: The current time (aware).
        until: When it ends (signal_brief.away.parse_until), or None: keep the end the owner
            gave earlier while it's on, else 3 days from now.
        note: A short note, at most 140 characters; "" keeps the current one while on.

    Raises:
        ValueError: The note breaks the text rules, or `until` isn't ahead.
        BriefLogError: The state couldn't be locked or written.
    """
    check_text("note", note, MAX_NOTE_CHARS)
    if until is not None and until <= now:
        raise ValueError("away mode's end has already passed")
    with state_lock(paths):
        # One that expired but wasn't ended yet ends properly first: this is a new away.
        old = _end_if_expired_locked(paths, now)
        current = old if old.get("on") else {}
        end, given = _new_end(current, now, until)
        record = {
            "on": True,
            "since": current.get("since") or to_iso(now),
            "until": to_iso(end),
            "until_given": given,
            "note": note or str(current.get("note", "")),
            "since_seq": _seq(current) if current else read_counters(paths).seq,
        }
        write_json_atomic(paths.away, record)
    return away_status(paths, now)


def _new_end(current: dict, now: datetime, until: datetime | None) -> tuple[datetime, bool]:
    """The end to store and whether the owner gave it: the new one, their earlier one, or 3 days."""
    if until is not None:
        return until, True
    kept = from_iso(current.get("until")) if current.get("until_given") else None
    return (kept, True) if kept is not None else (now + AWAY_WITHOUT_END, False)


def away_off(paths: BriefPaths, now: datetime) -> int | None:
    """End away mode ("I'm back") and mark a full brief due.

    Returns:
        How many entries were logged while away, or None if away mode was off.

    Raises:
        BriefLogError: The state couldn't be locked or written.
    """
    with state_lock(paths):
        record = read_json_object(paths.away)
        return _end_locked(paths, record, now) if record.get("on") else None


def away_status(paths: BriefPaths, now: datetime) -> AwayStatus:
    """Asleep, away or here, ending away mode first if its end has passed.

    Raises:
        BriefLogError: The state couldn't be read, or an expiry couldn't be written.
    """
    record = read_json_object(paths.away)
    if _has_expired(record, now):
        with state_lock(paths):
            record = _end_if_expired_locked(paths, now)
    ends_at = _ends_at(record)
    if _is_asleep(paths.sleep_state):
        state = "asleep"
    elif ends_at is not None:
        state = "away"
    else:
        return AwayStatus("here")
    note, given = str(record.get("note", "")), record.get("until_given") is True
    return AwayStatus(state, ends_at, note, _seq(record), given)


def held_count(paths: BriefPaths, since_seq: int) -> int:
    """How many entries (folded by key) were logged after `since_seq`."""
    return sum(1 for entry in current_entries(paths) if entry.seq > since_seq)


def _end_if_expired_locked(paths: BriefPaths, now: datetime) -> dict:
    """End away mode if it has expired; return the record as it now stands ({} once ended).

    Read again under the lock: another process may have ended it, or set a new end.
    """
    record = read_json_object(paths.away)
    if not _has_expired(record, now):
        return record
    _end_locked(paths, record, now)
    return {}


def _end_locked(paths: BriefPaths, record: dict, now: datetime) -> int:
    """Turn away mode off, log the 3-day expiry if that's why, mark a full brief due."""
    held = held_count(paths, _seq(record))
    write_json_atomic(paths.away, {"on": False})
    ends_at = _ends_at(record)
    if not record.get("until_given") and ends_at is not None and ends_at <= now:
        noun = "item" if held == 1 else "items"
        title = f"Away mode ended after 3 days, {held} {noun} held"
        # Our own title, so append_locked's unchecked path is fine.
        append_locked(paths, NewEntry("heads_up", title, key=f"away.expired:{_seq(record)}"), now)
    mark_due_locked(paths, now, "away_end")
    return held


def _ends_at(record: dict) -> datetime | None:
    """When the away mode in `record` ends, or None if it's off or unreadable."""
    return from_iso(record.get("until")) if record.get("on") else None


def _has_expired(record: dict, now: datetime) -> bool:
    ends_at = _ends_at(record)
    return ends_at is not None and ends_at <= now


def _seq(record: dict) -> int:
    seq = record.get("since_seq")
    return seq if isinstance(seq, int) else 0


def _is_asleep(sleep_state: Path) -> bool:
    """sleepmode's is_asleep flag; False if sleepmode has never run or its file is unreadable."""
    try:
        payload = json.loads(read_bytes_retrying(sleep_state))
    except (OSError, ValueError):
        return False
    return isinstance(payload, dict) and payload.get("is_asleep") is True
