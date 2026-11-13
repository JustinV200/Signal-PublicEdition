"""ack_delivery: the owner saw a delivery, so the bookmark moves, at most to its through.

The ack is recorded on the delivery in shown.json (the board hides on any ack
whose through reaches its delivery's). It drops the due full brief only if the
delivery was given at or after that brief was marked due: an ack of an older delivery
says nothing about the newer brief. An unknown id acks nothing.
"""

from datetime import datetime

from signal_brief.deliveries.shown import load_deliveries, save_deliveries_locked, with_ack
from signal_brief.log import advance_through_locked
from signal_brief.paths import BriefPaths
from signal_brief.presence import drop_due_locked
from signal_brief.store import state_lock


def ack_delivery(paths: BriefPaths, delivery_id: str, through: int, now: datetime) -> int | None:
    """Ack one delivery through min(`through`, the delivery's own through).

    Args:
        paths: The state files.
        delivery_id: b-<hash>.<n>.
        through: How far this ack reaches (a delivery's own through for a full ack).
        now: The time of the ack.

    Returns:
        The bookmark after the ack, or None if no delivery has that id.

    Raises:
        BriefLogError: The state couldn't be locked or written.
    """
    with state_lock(paths):
        deliveries = load_deliveries(paths)
        index = next((i for i, d in enumerate(deliveries) if d.id == delivery_id), None)
        if index is None:
            return None
        deliveries[index] = acked = with_ack(deliveries[index], through, now)
        save_deliveries_locked(paths, deliveries, now)
        bookmark = advance_through_locked(paths, acked.acked_through or 0)
        drop_due_locked(paths, acked.at)
        return bookmark
