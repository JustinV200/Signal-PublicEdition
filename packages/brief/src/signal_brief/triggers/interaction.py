"""on_interaction: what to offer the owner when the owner's present, by the brief's four rules.

Callers run it only when the owner's present (each surface decides that; the prompt hook
counts input within 5 s of the owner's prompt). It updates last_human_at and returns:

1. While away (or asleep): only rule 4.
2. "full" while a full brief is due, however long ago it was marked: it builds up
   until the owner sees it. The due flag drops only on an ack of a delivery given at or
   after it was marked (signal_brief.deliveries).
3. Morning: the day's first interaction from 04:00 to 12:00, unless a delivery
   given this morning was already acked, marks a full brief due for rule 2 (a
   general one until phase 3's morning composer). Last night's acked "brief me"
   doesn't count. It's spent for the day once checked.
4. "one_liner" after 6+ h since last_human_at, if something is unseen and no
   delivery since then reached the newest unseen item (an acked one reaches only
   as far as its ack).

Never an empty brief: with nothing to show, there's no offer. Whatever the offer,
the Interaction also says whether rule 4 holds, so a session that already got the
due brief can give the one-liner instead of nothing.
"""

from dataclasses import dataclass, replace
from datetime import datetime, time, timedelta

from signal_brief.away import away_status
from signal_brief.compose import Brief, compose
from signal_brief.deliveries import Delivery, load_deliveries
from signal_brief.paths import BriefPaths
from signal_brief.presence import DueBrief, Presence, read_presence, write_presence_locked
from signal_brief.store import state_lock

ONE_LINER_GAP = timedelta(hours=6)
MORNING_START = time(4, 0)
MORNING_END = time(12, 0)


@dataclass(frozen=True)
class Interaction:
    """What on_interaction decided.

    Attributes:
        offer: "full", "one_liner" or None.
        brief: The brief as composed for this interaction.
        due: For "full", the due brief it answers (a session gets one per due).
        gap_one_liner: Rule 4 holds, whatever the offer. Measured from the last
            interaction before this one, so it holds at most once per gap.
    """

    offer: str | None
    brief: Brief
    due: DueBrief | None = None
    gap_one_liner: bool = False


def on_interaction(paths: BriefPaths, now: datetime) -> Interaction:
    """Apply the rules for one present interaction and record it.

    Raises:
        BriefLogError: The state couldn't be read, locked or written.
    """
    is_away = away_status(paths, now).is_away  # may end an expired away first
    brief = compose(paths)
    with state_lock(paths):
        presence = read_presence(paths)
        deliveries = load_deliveries(paths)
        offer, presence, gap = decide_offer(presence, deliveries, brief, is_away, now)
        write_presence_locked(paths, replace(presence, last_human_at=now))
    return Interaction(offer, brief, presence.due if offer == "full" else None, gap)


def decide_offer(
    presence: Presence, deliveries: list[Delivery], brief: Brief, is_away: bool, now: datetime
) -> tuple[str | None, Presence, bool]:
    """The offer, the updated presence (due flag, morning day) and whether rule 4 holds; pure."""
    gap = _gap_holds(presence, deliveries, brief, now)
    gap_offer = "one_liner" if gap else None
    if is_away:
        return gap_offer, presence, gap
    presence = _check_morning(presence, deliveries, now)
    if presence.due is None:
        return gap_offer, presence, gap
    # No expiry: only an ack drops it, so a due brief is never lost unseen.
    return ("full" if brief.items else None), presence, gap


def one_liner_text(brief: Brief) -> str:
    """'You have a brief waiting: 3 things need you'."""
    count = len(brief.items)
    return f"You have a brief waiting: {count} {'thing needs' if count == 1 else 'things need'} you"


def _check_morning(presence: Presence, deliveries: list[Delivery], now: datetime) -> Presence:
    """Rule 3: the first check of the day in the morning window may mark a brief due."""
    today = now.date()
    if presence.morning_on == today or not MORNING_START <= now.time() < MORNING_END:
        return presence
    presence = replace(presence, morning_on=today)
    morning_start = datetime.combine(today, MORNING_START).astimezone()
    # Given and acked this morning: last night's brief, acked by this prompt, isn't it.
    if any(d.at >= morning_start and d.acked_at is not None for d in deliveries):
        return presence
    return replace(presence, due=DueBrief("general", now, "morning"))


def _gap_holds(presence: Presence, deliveries: list[Delivery], brief: Brief, now: datetime) -> bool:
    """Rule 4: a 6 h gap, and something unseen that wasn't given since.

    "Given since" means a delivery since last_human_at that reached the newest unseen
    item. Any delivery at all would be too much: the hook's own injection is stamped
    the same second as last_human_at, and an older brief doesn't hold what's new.
    """
    last = presence.last_human_at
    if last is not None and now - last < ONE_LINER_GAP:
        return False
    unseen = [item.seq for item in brief.items if item.seq > brief.through]
    if not unseen:
        return False
    newest = max(unseen)
    return last is None or not any(d.at >= last and _reached(d) >= newest for d in deliveries)


def _reached(delivery: Delivery) -> int:
    """How far a delivery got to the owner: its ack once acked, else all it showed.

    A relay that left an item out acks only up to it, so the item stays unseen and
    the delivery mustn't count as having given it.
    """
    return delivery.through if delivery.acked_through is None else delivery.acked_through
