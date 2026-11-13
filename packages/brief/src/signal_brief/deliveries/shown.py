"""shown.json: each delivery (one render on one surface) and its ack.

Only what the owner was given can be acked, so every render a surface gives the owner is
recorded as b-<hash>.<n> with its surface, the refs it showed and `through`: the
newest seq it showed or, if it cut an entry past the bookmark, the seq just
before the oldest such cut one. Open waits from before the bookmark don't count
for the cut: they're already seen, and would otherwise pin every ack below it.
It also records whether the render cut any such new entry, so an ack that only
repeats old waits can't count for a render that hid everything new. The last 50
deliveries are kept, none over 7 days old.
"""

import re
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from typing import Any

from signal_brief.compose import Brief, Render
from signal_brief.log import read_counters, write_counters
from signal_brief.paths import BriefPaths
from signal_brief.store import read_json_object, state_lock, write_json_atomic
from signal_brief.times import from_iso, to_iso

MAX_DELIVERIES = 50
MAX_DELIVERY_AGE = timedelta(days=7)
# Title words a relay must repeat next to the ref (signal_brief.deliveries.relay).
TITLE_WORD = re.compile(r"\w{4,}")
MAX_TITLE_WORDS = 8


@dataclass(frozen=True)
class ShownRef:
    """One ref a delivery showed: the seq it showed and its title's words."""

    seq: int
    words: tuple[str, ...]


@dataclass(frozen=True)
class Delivery:
    """One render given to the owner on one surface.

    Attributes:
        id: b-<hash>.<n>.
        surface: "session", "managed" (later "voice", "console", "board").
        at: When it was given.
        refs: The refs it showed.
        through: The furthest an ack of it may move the bookmark.
        session_id: The Claude session a prompt hook injected it into, else None.
        due_marked_at: The due brief it answered (ISO), so a session gets one per due.
        acked_through: The furthest it has been acked, or None.
        acked_at: When it was last acked, or None.
        cut_new: Its render cut an entry past the bookmark.
    """

    id: str
    surface: str
    at: datetime
    refs: dict[str, ShownRef]
    through: int
    session_id: str | None = None
    due_marked_at: str | None = None
    acked_through: int | None = None
    acked_at: datetime | None = None
    cut_new: bool = False

    @property
    def is_fully_acked(self) -> bool:
        """True once an ack reached its own through."""
        return self.acked_through is not None and self.acked_through >= self.through


@dataclass(frozen=True)
class DeliveryOrigin:
    """Where a delivery went: its surface, and for a hook injection the session and due."""

    surface: str
    session_id: str | None = None
    due_marked_at: str | None = None


def record_delivery(
    paths: BriefPaths, brief: Brief, render: Render[Any], origin: DeliveryOrigin, now: datetime
) -> Delivery:
    """Log one delivery of `render` and return it with its new id.

    Raises:
        BriefLogError: The state couldn't be locked or written.
    """
    refs = {e.ref: ShownRef(e.seq, _title_words(e.content.title)) for e in render.shown}
    with state_lock(paths):
        counters = read_counters(paths)
        counters.deliveries += 1
        write_counters(paths, counters)
        delivery = Delivery(
            id=f"{brief.id}.{counters.deliveries}",
            surface=origin.surface,
            at=now,
            refs=refs,
            through=delivery_through(brief, render),
            session_id=origin.session_id,
            due_marked_at=origin.due_marked_at,
            cut_new=any(entry.seq > brief.through for entry in render.cut),
        )
        save_deliveries_locked(paths, [*load_deliveries(paths), delivery], now)
    return delivery


def delivery_through(brief: Brief, render: Render[Any]) -> int:
    """The furthest an ack of this render may move the bookmark (see the module docstring)."""
    cut_new = [entry.seq for entry in render.cut if entry.seq > brief.through]
    if cut_new:
        return min(cut_new) - 1
    return max((entry.seq for entry in render.shown), default=brief.through)


def load_deliveries(paths: BriefPaths) -> list[Delivery]:
    """Every readable delivery in shown.json, oldest first. Raises BriefLogError."""
    payload = read_json_object(paths.shown).get("deliveries")
    loaded = [_from_payload(item) for item in payload] if isinstance(payload, list) else []
    return [delivery for delivery in loaded if delivery is not None]


def save_deliveries_locked(paths: BriefPaths, deliveries: list[Delivery], now: datetime) -> None:
    """Replace shown.json, keeping the last 50 under 7 days old. Call under the lock."""
    kept = [d for d in deliveries if now - d.at <= MAX_DELIVERY_AGE][-MAX_DELIVERIES:]
    write_json_atomic(paths.shown, {"deliveries": [_to_payload(d) for d in kept]})


def with_ack(delivery: Delivery, through: int, now: datetime) -> Delivery:
    """`delivery` acked through `through` (never past its own, never backwards)."""
    capped = min(through, delivery.through)
    return replace(delivery, acked_through=max(capped, delivery.acked_through or 0), acked_at=now)


def _title_words(title: str) -> tuple[str, ...]:
    words = dict.fromkeys(TITLE_WORD.findall(title.casefold()))  # ordered, no repeats
    return tuple(words)[:MAX_TITLE_WORDS]


def _to_payload(delivery: Delivery) -> dict[str, Any]:
    return {
        "id": delivery.id,
        "surface": delivery.surface,
        "at": to_iso(delivery.at),
        "refs": {ref: {"seq": s.seq, "words": list(s.words)} for ref, s in delivery.refs.items()},
        "through": delivery.through,
        "session_id": delivery.session_id,
        "due": delivery.due_marked_at,
        "cut_new": delivery.cut_new,
        "acked": None
        if delivery.acked_at is None
        else {"at": to_iso(delivery.acked_at), "through": delivery.acked_through},
    }


def _from_payload(item: object) -> Delivery | None:
    """A Delivery from shown.json, or None if it's malformed (a hand edit)."""
    if not isinstance(item, dict) or (at := from_iso(item.get("at"))) is None:
        return None
    acked = item.get("acked") if isinstance(item.get("acked"), dict) else {}
    try:
        refs = {
            str(ref): ShownRef(int(shown["seq"]), tuple(str(word) for word in shown["words"]))
            for ref, shown in item["refs"].items()
        }
        return Delivery(
            id=str(item["id"]),
            surface=str(item["surface"]),
            at=at,
            refs=refs,
            through=int(item["through"]),
            session_id=_optional_text(item.get("session_id")),
            due_marked_at=_optional_text(item.get("due")),
            acked_through=int(acked["through"]) if "through" in acked else None,
            acked_at=from_iso(acked.get("at")),
            cut_new=item.get("cut_new") is True,
        )
    except (KeyError, TypeError, ValueError, AttributeError):
        return None


def _optional_text(value: object) -> str | None:
    return value if isinstance(value, str) else None
