"""Public API of audiohub.loop.phrases: pure parsing of what the user said.

No I/O and no state: wake-phrase matching, stop commands and
echoes of Claude's own speech.
The rest of audiohub.loop imports these from here.
"""

from .echo import is_echo, is_echo_during_speech, is_echo_of_ending, is_exact_ending
from .stop import is_stop_command
from .tokens import has_words
from .wake import match_wake

__all__ = [
    "has_words",
    "is_echo",
    "is_echo_during_speech",
    "is_echo_of_ending",
    "is_exact_ending",
    "is_stop_command",
    "match_wake",
]
