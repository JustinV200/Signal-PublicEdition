"""The digest's memory between runs: windows, announced keys, failures, files to review.

Kept as JSON in the gitignored state file. Only this runner reads and writes it; the
model can't (its file tools are confined to life/), and nothing in it is shown to the
model. Each run searches `after:<searched_until - overlap> before:<run start>` per
account, and an account's `searched_until` moves forward only when the run says it
finished it.
"""

import json
import logging
import os
import re
from collections.abc import Iterable
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import NamedTuple

log = logging.getLogger(__name__)

# Every stored key: a kind, then one or two lowercase slug parts, e.g.
# "overdue|hist-205-practice-quiz" or "signin|school|2026-10-19-to-10-25".
KEY_PATTERN = re.compile(r"[a-z]{2,10}(\|[a-z0-9-]{1,80}){1,2}")
# A corrupt state file is copied next to itself with this suffix before a fresh start
# (a later corrupt file overwrites the copy).
CORRUPT_SUFFIX = ".corrupt"


class Pending(NamedTuple):
    """An announcement a run couldn't deliver: its key, sentence and first try (Unix s)."""

    key: str
    sentence: str
    first_seen: int


@dataclass(frozen=True)
class DigestState:
    """What earlier runs did.

    searched_until: alias -> Unix seconds up to which that account is digested.
    announced: announced key -> Unix seconds when it was first spoken.
    failures: consecutive failed runs (0 after a success).
    needs_review: life/ paths with an edit the KB guard couldn't check, announced
    every run until they've been reviewed (kb/review.py). A run flags every file
    it may edit before claude starts, and clears them once the guard has run.
    was_reset: the state file was corrupt, so this is a fresh start and its flags
    are gone (the runner announces it). Only for this run: it isn't saved.
    pending: announcements a run couldn't deliver (the hub was down), retried on
    later runs until spoken or stale (steps/outcome.py).
    """

    searched_until: dict[str, int] = field(default_factory=dict)
    announced: dict[str, int] = field(default_factory=dict)
    failures: int = 0
    needs_review: tuple[str, ...] = ()
    was_reset: bool = False
    pending: tuple[Pending, ...] = ()


class Lookback(NamedTuple):
    """How far back windows reach, in seconds: first run, at most ever, and the overlap."""

    first_run_s: int
    max_s: int
    overlap_s: int


class KeyRetention(NamedTuple):
    """How long announced keys are remembered (seconds) and how many are kept at most."""

    keep_s: int
    max_keys: int


@dataclass(frozen=True)
class Window:
    """One account's Gmail search window this run, in Unix seconds (receive time).

    skipped_since: the account's old searched_until when the max lookback cut the
    window short (mail between it and `after` won't be read), else None.
    """

    after: int
    before: int
    skipped_since: int | None = None


def is_valid_key(key: str) -> bool:
    """True if key has the strict stored-key form (KEY_PATTERN)."""
    return KEY_PATTERN.fullmatch(key) is not None


def load_state(path: Path, max_keys: int, keep_copy: bool = True) -> DigestState:
    """Read the state file. A missing file is a first run.

    A corrupt file (not a JSON object) is logged and treated as a first run, with
    was_reset set: the lookback caps the re-read, and the routine skips lines
    already in the KB. It's copied to <name>.corrupt first, unless keep_copy is
    False (a dry run, which writes nothing). Malformed keys are dropped and at most
    max_keys (the newest) are kept.

    Raises OSError if the file is there but can't be read, or the copy can't be
    written. A fresh start would drop its needs_review flags, so the file is left
    as it is and the run stops: run_once can't record that crash, so it says so out
    loud and raises.
    """
    try:
        data = path.read_bytes()
    except FileNotFoundError:
        return DigestState()
    try:
        raw = json.loads(data)
    except ValueError:  # bad JSON or bad UTF-8
        raw = None
    if not isinstance(raw, dict):
        if keep_copy:
            backup = path.with_name(path.name + CORRUPT_SUFFIX)
            backup.write_bytes(data)
            log.error("state file %s is corrupt; copied it to %s, starting fresh", path, backup)
        else:
            log.error("state file %s is corrupt; a real run would reset it", path)
        return DigestState(was_reset=True)
    announced = {k: t for k, t in _int_map(raw.get("announced")).items() if is_valid_key(k)}
    failures = raw.get("failures")
    return DigestState(
        searched_until=_int_map(raw.get("searched_until")),
        announced=_newest(announced, max_keys),
        failures=failures if _is_int(failures) and failures >= 0 else 0,
        needs_review=_str_tuple(raw.get("needs_review")),
        pending=_pending(raw.get("pending")),
    )


def save_state(path: Path, state: DigestState) -> None:
    """Write the state atomically (temp file in the same folder, then replace)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".tmp")
    body = {
        "searched_until": state.searched_until,
        "announced": state.announced,
        "failures": state.failures,
        "needs_review": list(state.needs_review),
        "pending": [p._asdict() for p in state.pending],
    }
    temp.write_text(json.dumps(body, indent=2, sort_keys=True), encoding="utf-8")
    os.replace(temp, path)


def search_windows(
    state: DigestState, aliases: tuple[str, ...], now: int, lookback: Lookback
) -> dict[str, Window]:
    """This run's window for every alias.

    A never-seen account starts lookback.first_run_s back; a known one starts
    lookback.overlap_s before its searched_until. No window starts more than
    lookback.max_s back; when that cuts one short, its skipped_since says so.
    """
    earliest = now - lookback.max_s
    windows = {}
    for alias in aliases:
        last = state.searched_until.get(alias)
        wanted = now - lookback.first_run_s if last is None else last - lookback.overlap_s
        skipped_since = last if last is not None and wanted < earliest else None
        windows[alias] = Window(max(wanted, earliest), now, skipped_since)
    return windows


def advance_windows(
    state: DigestState, windows: dict[str, Window], completed: tuple[str, ...]
) -> DigestState:
    """The state after a successful run.

    Completed accounts move up to their window's end; others keep theirs, so the
    next run retries them. The failure count resets.
    """
    searched_until = dict(state.searched_until)
    for alias, window in windows.items():
        if alias in completed:
            searched_until[alias] = window.before
    return replace(state, searched_until=searched_until, failures=0)


def record_failure(state: DigestState) -> DigestState:
    """The state after a failed run: windows untouched, one more consecutive failure."""
    return replace(state, failures=state.failures + 1)


def remember_announced(
    state: DigestState, keys: Iterable[str], now: int, retention: KeyRetention
) -> DigestState:
    """Add keys first spoken at `now`, forget ones older than retention.keep_s, and keep
    the newest retention.max_keys.

    Keys that don't match KEY_PATTERN are dropped (logged): only the runner makes
    keys, so one would be a bug.
    """
    announced = {k: t for k, t in state.announced.items() if t >= now - retention.keep_s}
    for key in keys:
        if is_valid_key(key):
            announced.setdefault(key, now)
        else:
            log.warning("not storing malformed announced key %r", key)
    return replace(state, announced=_newest(announced, retention.max_keys))


def _newest(announced: dict[str, int], max_keys: int) -> dict[str, int]:
    """The max_keys most recently announced entries."""
    newest = sorted(announced.items(), key=lambda item: item[1], reverse=True)
    return dict(newest[:max_keys])


def _is_int(value: object) -> bool:
    """True for a real int (bool is an int subclass in Python, so exclude it)."""
    return isinstance(value, int) and not isinstance(value, bool)


def _str_tuple(value: object) -> tuple[str, ...]:
    """Keep only the non-empty strings of a list, sorted and without repeats."""
    if not isinstance(value, list):
        return ()
    return tuple(sorted({v for v in value if isinstance(v, str) and v}))


def _pending(value: object) -> tuple[Pending, ...]:
    """Keep only well-formed pending entries (valid key, non-empty sentence, int time)."""
    if not isinstance(value, list):
        return ()
    return tuple(
        Pending(item["key"], item["sentence"], item["first_seen"])
        for item in value
        if isinstance(item, dict)
        and is_valid_key(str(item.get("key")))
        and isinstance(item.get("sentence"), str)
        and item["sentence"]
        and _is_int(item.get("first_seen"))
    )


def _int_map(value: object) -> dict[str, int]:
    """Keep only str -> int entries; the file is ours, but validate it anyway."""
    if not isinstance(value, dict):
        return {}
    return {k: v for k, v in value.items() if isinstance(k, str) and _is_int(v)}
