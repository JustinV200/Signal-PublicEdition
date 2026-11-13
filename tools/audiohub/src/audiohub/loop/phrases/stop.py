"""Spoken stop commands: "Claude, stop" and "Claude, cancel" interrupt Claude.

Only a request that is nothing but a stop command counts, so "Claude, stop
the music" still goes to the brain as an ordinary request.
"""

from .tokens import words

# Each command is matched against the whole request, word for word.
_STOP_COMMANDS = frozenset(
    {
        ("stop",), ("cancel",), ("stop", "it"), ("stop", "that"), ("cancel", "that"),
        ("never", "mind"), ("nevermind",), ("stop", "talking"), ("be", "quiet"),
        ("shut", "up"), ("quiet",), ("enough",), ("thats", "enough"),
    }
)  # fmt: skip
# Politeness around a command ("stop now, please") doesn't change it.
_COURTESY_WORDS = frozenset({"please", "now", "just", "ok", "okay", "thanks"})


def is_stop_command(request: str) -> bool:
    """Say whether a request (wake phrase already stripped) asks Claude to stop.

    Args:
        request: e.g. "stop", "Cancel that, please." or "stop the music".

    Returns:
        True only when the request is a stop command and nothing more.
    """
    command = tuple(word for word in words(request) if word not in _COURTESY_WORDS)
    return command in _STOP_COMMANDS
