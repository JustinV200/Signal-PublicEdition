"""presence.json: when the owner last interacted, the due full brief, and the morning rule's day.

Read and replaced under the log's lock. Away's end (and, later, sleepmode's wake)
marks a full brief due; an ack of a delivery given at or after that drops it
(signal_brief.deliveries).
"""

from dataclasses import dataclass, replace
from datetime import date, datetime

from signal_brief.paths import BriefPaths
from signal_brief.store import read_json_object, write_json_atomic
from signal_brief.times import from_iso, to_iso


@dataclass(frozen=True)
class DueBrief:
    """A full brief waiting for the owner's next interaction.

    Attributes:
        kind: The brief to give ("general" until the morning composer lands).
        marked_at: When it was marked. It never expires: only an ack of a delivery
            given at or after this drops it.
        reason: Why ("morning", "away_end"), for logs.
    """

    kind: str
    marked_at: datetime
    reason: str


@dataclass(frozen=True)
class Presence:
    """The state the interaction rules (signal_brief.triggers) read and update."""

    last_human_at: datetime | None = None
    due: DueBrief | None = None
    morning_on: date | None = None


def read_presence(paths: BriefPaths) -> Presence:
    """presence.json, or an empty Presence. Raises BriefLogError if unreadable."""
    payload = read_json_object(paths.presence)
    return Presence(
        last_human_at=from_iso(payload.get("last_human_at")),
        due=_due(payload.get("due")),
        morning_on=_date(payload.get("morning_on")),
    )


def write_presence_locked(paths: BriefPaths, presence: Presence) -> None:
    """Replace presence.json. Call under the log's lock. Raises BriefLogError."""
    due = presence.due
    write_json_atomic(
        paths.presence,
        {
            "last_human_at": to_iso(presence.last_human_at) if presence.last_human_at else None,
            "due": {"kind": due.kind, "marked_at": to_iso(due.marked_at), "reason": due.reason}
            if due
            else None,
            "morning_on": presence.morning_on.isoformat() if presence.morning_on else None,
        },
    )


def mark_due_locked(paths: BriefPaths, now: datetime, reason: str) -> None:
    """Mark a general full brief due now. Call under the log's lock. Raises BriefLogError."""
    presence = read_presence(paths)
    write_presence_locked(paths, replace(presence, due=DueBrief("general", now, reason)))


def drop_due_locked(paths: BriefPaths, given_at: datetime) -> None:
    """Drop the due brief if a delivery given at `given_at` could have shown it.

    An ack of a delivery given before the brief was marked due (last night's "brief
    me", or one from before away mode ended) says nothing about the newer brief, so
    it stays due. Call under the log's lock.

    Raises:
        BriefLogError: presence.json couldn't be read or written.
    """
    presence = read_presence(paths)
    if presence.due is not None and given_at >= presence.due.marked_at:
        write_presence_locked(paths, replace(presence, due=None))


def _due(value: object) -> DueBrief | None:
    if not isinstance(value, dict) or not isinstance(value.get("kind"), str):
        return None
    marked_at = from_iso(value.get("marked_at"))
    return DueBrief(value["kind"], marked_at, str(value.get("reason", ""))) if marked_at else None


def _date(value: object) -> date | None:
    try:
        return date.fromisoformat(value) if isinstance(value, str) else None
    except ValueError:
        return None
