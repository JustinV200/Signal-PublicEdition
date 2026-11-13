"""Public API of audiohub.loop: the voice conversation loop and its building blocks.

- phrases: wake-phrase matching, stop commands, echo checks (pure)
- hearing: frames -> segmenter -> Whisper -> transcripts
- VoiceOutput: clean -> split -> synthesize -> play, with music ducked
- MusicPause: pauses the music while the user talks with Claude
- Conversation: everything wired together, plus the kernel's IPC server

Other packages (the CLI) import from here only.
"""

from .conversation import (
    Conversation,
    ConversationParts,
    ConversationState,
    HubIo,
    HubStartError,
    Phase,
    build_parts,
)
from .factories import create_hearing, create_voice_output
from .hearing import FrameSource, Heard, Hearing, WavFrameSource
from .music_pause import HubActivity, MusicPause
from .phrases import is_stop_command, match_wake
from .status import StatusLine, format_duration, quote
from .voice_output import VoiceOutput

__all__ = [
    "Conversation",
    "ConversationParts",
    "ConversationState",
    "FrameSource",
    "Hearing",
    "Heard",
    "HubActivity",
    "HubIo",
    "HubStartError",
    "MusicPause",
    "Phase",
    "StatusLine",
    "VoiceOutput",
    "WavFrameSource",
    "build_parts",
    "create_hearing",
    "create_voice_output",
    "format_duration",
    "is_stop_command",
    "match_wake",
    "quote",
]
