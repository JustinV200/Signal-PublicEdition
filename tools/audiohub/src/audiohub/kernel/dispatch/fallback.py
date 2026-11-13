"""The deterministic fallback policy, and the speaking order every delivery path shares.

The fallback is used whenever Sonnet can't be trusted or reached.
It delivers every pending message, verbatim, in `speaking_order`, so a
timeout or a bad reply never loses a message.
"""

from collections.abc import Sequence

from ..messages import PRIORITY_RANK, Decision, OutboundMessage

FALLBACK_REASON = "fallback: speaking order, verbatim"


def speaking_order(messages: Sequence[OutboundMessage]) -> list[OutboundMessage]:
    """Sort messages into the order to speak them.

    Claude's direct replies come first (they answer what the user just said),
    then everything else by priority. sorted() is stable, so messages in the
    same group keep their arrival order.

    Args:
        messages: Messages in arrival order.

    Returns:
        The same messages, in speaking order.
    """
    return sorted(messages, key=lambda m: (not m.is_direct_reply, PRIORITY_RANK[m.priority]))


def fallback_policy(pending: Sequence[OutboundMessage]) -> list[Decision]:
    """Deliver everything in `pending`, verbatim, in speaking order.

    Args:
        pending: Messages waiting to be spoken, oldest arrival first.

    Returns:
        One "deliver" decision per message, with no replacement text, in the
        order they should be spoken.
    """
    return [Decision(m.id, "deliver", None, FALLBACK_REASON) for m in speaking_order(pending)]
