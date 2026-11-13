"""Public API of audiohub.loop.conversation: the voice hub and its state machine.

`Conversation` wires hearing, the brain, the kernel and the voice output
together. The parts are importable for tests and for alternative wiring.
"""

from .conversation import Conversation, HubStartError
from .outbox import BACKGROUND_SOURCE, CLAUDE_SOURCE, HUB_SOURCE
from .parts import ConversationParts, HubIo, build_parts
from .routing import (
    Ask,
    Attend,
    BargeIn,
    Cancel,
    ConversationState,
    Echo,
    Ignore,
    Phase,
    Route,
)
from .turns import VoiceBrain

__all__ = [
    "BACKGROUND_SOURCE",
    "CLAUDE_SOURCE",
    "HUB_SOURCE",
    "Ask",
    "Attend",
    "BargeIn",
    "Cancel",
    "Conversation",
    "ConversationParts",
    "ConversationState",
    "Echo",
    "HubIo",
    "HubStartError",
    "Ignore",
    "Phase",
    "Route",
    "VoiceBrain",
    "build_parts",
]
