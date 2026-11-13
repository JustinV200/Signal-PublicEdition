"""The state side of a run's end: speak its announcements once, and record a crash.

Both runners call announce_once at the end of every run, and the digest calls
record_crash when a run crashes. Announced keys are stored only once the hub has
queued the message. When the hub is down, the run's items (everything but its
one-run alerts, keyed by the run's start: reset, review, guard, failure...) are kept
in the state's pending list and spoken first on later runs, until spoken or
PENDING_KEEP_S old. The one-run alerts aren't retried. A
crash counts as a failed run, so its review and failure alerts are spoken as on any
failed run. A crash that can't read the state file says so plainly instead.
"""

import logging
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path

from mail_digest.announce import Announcement, compose, fresh_announcements
from mail_digest.kb import GuardReport
from mail_digest.memory import (
    DigestState,
    KeyRetention,
    Pending,
    load_state,
    record_failure,
    remember_announced,
    save_state,
)
from mail_digest.settings import (
    ANNOUNCED_KEEP_S,
    MAX_ANNOUNCED_KEYS,
    MAX_SPOKEN_ITEMS,
    PENDING_KEEP_S,
)
from mail_digest.steps.notices import DIGEST_NAME, failure_alert, kb_alerts

log = logging.getLogger(__name__)

RETENTION = KeyRetention(ANNOUNCED_KEEP_S, MAX_ANNOUNCED_KEYS)
# Spoken when a crashed run can't even read the state file.
STATE_UNUSABLE = "The mail digest can't use its state file, so it stopped. Check its log."


def announce_once(
    state: DigestState,
    notices: list[Announcement],
    notify: Callable[[str], bool],
    now: int,
    closing: str = "",
    name: str = DIGEST_NAME,
) -> DigestState:
    """Speak what's new once, and remember its keys only if the hub queued the message.

    notify(text) returns True once the hub queued it. closing is a sentence always
    spoken last, after the new items (the checker's done line, since the owner is
    waiting); it has no key. name is the runner, as spoken in the "plus N more" hint.
    Earlier undelivered items go after this run's one-run alerts and before its
    other items. Returns state with the spoken keys stored as first spoken at now
    (Unix seconds) and the pending list updated; the caller saves it.
    """
    pending = [
        p
        for p in state.pending
        if p.first_seen >= now - PENDING_KEEP_S and p.key not in state.announced
    ]
    alerts = [n for n in notices if _is_one_run(n, now)]
    items = [n for n in notices if not _is_one_run(n, now)]
    # This run's sentence for a key beats a stored one (it's more up to date).
    item_keys = {n.key for n in items}
    retries = [Announcement(p.key, p.sentence) for p in pending if p.key not in item_keys]
    candidates = [*alerts, *retries, *items]
    text, keys = compose(candidates, state.announced, MAX_SPOKEN_ITEMS, f"Check the {name} log.")
    text = f"{text} {closing}".strip()
    delivered = bool(text) and notify(text)
    if delivered:
        log.info("announced %r: %r", list(keys), text)
        pending = [p for p in pending if p.key not in keys]
    elif text:
        log.warning("announcement not delivered, will retry next run: %r", list(keys))
        # A fresh item replaces a stored one with its key, but expiry still runs
        # from the first attempt.
        first_seen = {p.key: p.first_seen for p in pending}
        fresh = fresh_announcements(items, state.announced)
        fresh_keys = {a.key for a in fresh}
        pending = [p for p in pending if p.key not in fresh_keys]
        pending += [Pending(a.key, a.sentence, first_seen.get(a.key, now)) for a in fresh]
    stored = keys if delivered else ()
    state = replace(state, pending=tuple(pending))
    return remember_announced(state, stored, now, RETENTION)


def _is_one_run(notice: Announcement, now: int) -> bool:
    """True for an alert keyed by this run's start (only said on this run, never retried)."""
    return notice.key.endswith(f"|{now}")


def record_crash(state_path: Path, notify: Callable[[str], bool], run_start: int) -> None:
    """Count a crashed run as a failed one, and speak its alerts.

    That's the review alert while a file is flagged (as on every run), and the
    failure alert when it's due. Raises OSError if the state file can't be read or
    written. If it can't be read, STATE_UNUSABLE is spoken first.
    """
    try:
        state = load_state(state_path, MAX_ANNOUNCED_KEYS)
    except OSError:
        # With no state there's no failure count or spoken keys to go by, so this
        # is said on every run until the file can be read again.
        notify(STATE_UNUSABLE)
        raise
    state = record_failure(state)
    notices = kb_alerts(GuardReport(), state, run_start)
    alert = failure_alert(state.failures, run_start)
    notices += [alert] if alert else []
    save_state(state_path, announce_once(state, notices, notify, run_start))
