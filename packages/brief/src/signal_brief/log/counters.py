"""counters.json: the next seq, each ref letter's count, the delivery count, last compaction.

Every count only goes forward and outlives compaction, so a ref never moves and
never names two things. Read and written under the log's lock.
"""

from dataclasses import dataclass, field
from datetime import datetime

from signal_brief.paths import BriefPaths
from signal_brief.store import read_json_object, write_json_atomic
from signal_brief.times import from_iso, to_iso


@dataclass
class Counters:
    """The counts, as read; callers bump their own copy and write it back.

    Attributes:
        seq: The last seq handed out.
        refs: Each ref letter's last count.
        deliveries: The last delivery number (the <n> in b-<hash>.<n>).
        compacted_at: When the log was last compacted, or None.
    """

    seq: int = 0
    refs: dict[str, int] = field(default_factory=dict)
    deliveries: int = 0
    compacted_at: datetime | None = None


def read_counters(paths: BriefPaths) -> Counters:
    """The counters, or zeros if there's no file yet. Raises BriefLogError if unreadable."""
    payload = read_json_object(paths.counters)
    refs = payload.get("refs")
    return Counters(
        seq=_count(payload.get("seq")),
        refs={k: _count(v) for k, v in refs.items()} if isinstance(refs, dict) else {},
        deliveries=_count(payload.get("deliveries")),
        compacted_at=from_iso(payload.get("compacted_at")),
    )


def write_counters(paths: BriefPaths, counters: Counters) -> None:
    """Replace counters.json. Call under the log's lock. Raises BriefLogError."""
    compacted = to_iso(counters.compacted_at) if counters.compacted_at else None
    write_json_atomic(
        paths.counters,
        {
            "seq": counters.seq,
            "refs": counters.refs,
            "deliveries": counters.deliveries,
            "compacted_at": compacted,
        },
    )


def _count(value: object) -> int:
    return value if isinstance(value, int) and value >= 0 else 0
