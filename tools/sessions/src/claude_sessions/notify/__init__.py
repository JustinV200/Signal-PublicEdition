"""Public API of claude_sessions.notify: the wording of the voice notes sent about sessions.

Delivery is signal_hub_notify's job (packages/hubnotify); this package only
says what the owner hears.
"""

from claude_sessions.notify.messages import (
    approval_needed_note,
    session_failed_note,
    source_for,
    turn_finished_note,
)

__all__ = [
    "approval_needed_note",
    "session_failed_note",
    "source_for",
    "turn_finished_note",
]
