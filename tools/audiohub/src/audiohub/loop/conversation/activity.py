"""`ConversationActivity`: the hub's state as the music pause sees it (loop/music_pause.py).

Read live from the conversation state machine and the kernel each time it is
asked, so the music pause keeps no copy of either.
"""

import time

from audiohub.kernel import Kernel

from .routing import ConversationState, Phase


class ConversationActivity:
    """Answers MusicPause's HubActivity questions from the hub's state and kernel."""

    def __init__(self, state: ConversationState, kernel: Kernel) -> None:
        """Read from these two; nothing is copied.

        Args:
            state: The conversation state machine (phase, follow-up window).
            kernel: Holds the messages not yet spoken.
        """
        self._state = state
        self._kernel = kernel

    def is_busy(self) -> bool:
        """Whether a brain turn runs, or speech (or its echo tail) is playing."""
        return self._state.phase is not Phase.LISTENING

    def is_conversation_open(self) -> bool:
        """Whether the follow-up window is open, or messages wait in the kernel to be spoken.

        Pending messages count because a reply can wait 3-8 s for the kernel's
        dispatcher after the turn ends, and the music shouldn't resume in that gap.
        """
        return self._state.is_in_follow_up(time.monotonic()) or self._kernel.pending_count > 0
