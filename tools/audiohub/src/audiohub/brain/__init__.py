"""Public API of audiohub.brain: the Claude Code session the user talks to by voice.

Other packages import from here only. SDK-specific code lives in the sdk_*
modules and doesn't leak out of this package.
"""

from audiohub.brain.claude_brain import ClaudeBrain
from audiohub.brain.connection import BrainSession, SessionFactory
from audiohub.brain.events import (
    BrainEvent,
    InjectedTurnDone,
    ReplyText,
    SessionEvent,
    TurnActivity,
    TurnDone,
)
from audiohub.brain.turn_router import BackgroundTextHandler
from audiohub.brain.turn_watchdog import TurnStalledError
from audiohub.brain.voice_prompt import VOICE_SYSTEM_APPEND

__all__ = [
    "VOICE_SYSTEM_APPEND",
    "BackgroundTextHandler",
    "BrainEvent",
    "BrainSession",
    "ClaudeBrain",
    "InjectedTurnDone",
    "ReplyText",
    "SessionEvent",
    "SessionFactory",
    "TurnActivity",
    "TurnDone",
    "TurnStalledError",
]
