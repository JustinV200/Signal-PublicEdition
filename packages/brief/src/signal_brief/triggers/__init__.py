"""Public API of signal_brief.triggers: what to offer the owner on a present interaction."""

from signal_brief.triggers.interaction import (
    ONE_LINER_GAP,
    Interaction,
    decide_offer,
    on_interaction,
    one_liner_text,
)

__all__ = [
    "ONE_LINER_GAP",
    "Interaction",
    "decide_offer",
    "on_interaction",
    "one_liner_text",
]
