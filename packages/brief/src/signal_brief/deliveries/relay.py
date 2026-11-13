"""relayed_through: how far a Claude session's replies ack a delivery it was given.

A session only acks what Claude actually passed on: a summary that drops refs
doesn't ack them. A ref counts as relayed when one line of Claude's reply text has
it as a word and, if its title has words of 4+ letters (not common filler), one of
them too, so "D1 to D9 noted" acks nothing. Only refs past the bookmark can hold
the ack back; open waits the owner would already seen can't pin it.
"""

import re

from signal_brief.deliveries.shown import Delivery, ShownRef

WORD = re.compile(r"\w+")
# Title words too common to show the item was passed on.
FILLER_WORDS = frozenset(
    {
        "about", "after", "also", "before", "been", "from", "have", "into", "just",
        "more", "only", "over", "some", "than", "that", "their", "them", "then",
        "there", "they", "this", "were", "what", "when", "will", "with", "your",
    }
)  # fmt: skip


def relayed_through(delivery: Delivery, replies: list[str], bookmark: int) -> int | None:
    """The seq the replies ack `delivery` through, or None if they relayed none of it.

    Args:
        delivery: A delivery the session was given.
        replies: Claude's assistant text since the delivery (no thinking, tool calls
            or tool results).
        bookmark: The bookmark's through now.

    Returns:
        Through the seq just before the oldest ref past the bookmark missing from the
        replies, capped at the delivery's own through. None if nothing counting was
        relayed: when the delivery has refs past the bookmark, one of those must be,
        since repeating an old wait alone shows nothing new was passed on. A delivery
        that showed no new ref but cut some never acks: everything new was hidden.
    """
    lines = [line for text in replies for line in text.splitlines()]
    relayed = {ref for ref, shown in delivery.refs.items() if _is_relayed(ref, shown, lines)}
    new_refs = {ref for ref, shown in delivery.refs.items() if shown.seq > bookmark}
    if not new_refs and delivery.cut_new:
        return None
    if not (relayed & new_refs if new_refs else relayed):
        return None
    missing = [delivery.refs[ref].seq - 1 for ref in new_refs - relayed]
    return min([delivery.through, *missing])


def _is_relayed(ref: str, shown: ShownRef, lines: list[str]) -> bool:
    """True if a line names `ref` and, when the title has telling words, one of them."""
    ref_pattern = re.compile(rf"\b{re.escape(ref)}\b")
    telling = set(shown.words) - FILLER_WORDS
    for line in lines:
        if not ref_pattern.search(line):
            continue
        if not telling or telling & set(WORD.findall(line.casefold())):
            return True
    return False
