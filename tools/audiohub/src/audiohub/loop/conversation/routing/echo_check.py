"""`EchoCheck`: did the mic just hear Claude's own speech? Decided by when the utterance began.

Part of the routing: `ConversationState.route` asks this first, and drops an
echo before any other rule applies. The text matchers are in `loop/phrases`;
this picks which one applies, and what Claude said that it is compared with.

With barge-in on, an utterance begun while Claude was still audible to the
user (before `reply_after_s` past its audio end, and before any barge-in cut
it) is an echo if it repeats Claude's recent sentences
(`is_echo_during_speech`). One begun in the rest of the echo tail is a reply:
dropped only if it reads as Claude's last words (`is_echo_of_ending`), or, for
a stop or wake phrase, also if it mostly repeats Claude's recent sentences.
After the tail, `is_echo` (3+ words, mostly Claude's last few) drops a stop or
wake phrase, and any other reply only if it is also exactly Claude's last
words (`is_exact_ending`). With barge-in off, `is_echo` alone decides, as ever.
"""

from ...phrases import (
    is_echo,
    is_echo_during_speech,
    is_echo_of_ending,
    is_exact_ending,
    is_stop_command,
    match_wake,
)
from .routes import Echo
from .speech_window import SpeechHistory

# Echoes arrive right after the mic reopens; later repeats are the user's own.
ECHO_WINDOW_S = 4.0


class EchoCheck:
    """Finds echoes of Claude's speech, from its timing and the text it last spoke."""

    def __init__(
        self,
        speech: SpeechHistory,
        wake_phrases: tuple[str, ...],
        *,
        is_barge_in: bool,
        echo_lag_s: float,
    ) -> None:
        """Check against `speech`, which the caller keeps up to date.

        Args:
            speech: When Claude spoke which sentence (shared with the caller).
            wake_phrases: The wake phrases, to spot a wake request.
            is_barge_in: Whether the mic stays live while Claude speaks.
            echo_lag_s: How long a sentence may still reach the mic after it
                stopped playing (`audio.echo_tail_s`).
        """
        self._speech = speech
        self._wake_phrases = wake_phrases
        self._is_barge_in = is_barge_in
        self._echo_lag_s = echo_lag_s
        self._last_spoken = ""
        self._speech_ended_at: float | None = None

    def speech_finished(self, now: float, spoken_text: str) -> None:
        """Claude's speech and its echo tail ended at `now`, having said `spoken_text`."""
        self._last_spoken = spoken_text
        self._speech_ended_at = now

    def find(self, transcript: str, heard_at: float, heard_until: float) -> Echo | None:
        """An Echo if the transcript repeats what Claude said around then, else None.

        Args:
            transcript: What the user said.
            heard_at: When they started saying it.
            heard_until: When they finished.
        """
        if self._is_barge_in and self._speech.overlaps(heard_at, heard_until):
            return self._find_over_speech(transcript, heard_at, heard_until)
        if self._speech_ended_at is None or heard_at > self._speech_ended_at + ECHO_WINDOW_S:
            return None
        if self._is_echo_after_tail(transcript):
            return self._echo(self._last_spoken, heard_at)
        return None

    def _is_echo_after_tail(self, transcript: str) -> bool:
        """Whether a transcript begun after the echo tail is Claude's last words."""
        spoken = self._last_spoken
        if not self._is_barge_in:
            return is_echo(transcript, spoken)
        # With barge-in, Claude's voice no longer reaches the live mic, so a
        # late echo is exactly its last words: one word off is a reply. A stop
        # or wake phrase keeps the loose check: a false one costs more than
        # saying it again.
        is_loose = self._has_command(transcript)
        return is_echo(transcript, spoken) and (is_loose or is_exact_ending(transcript, spoken))

    def _find_over_speech(
        self, transcript: str, heard_at: float, heard_until: float
    ) -> Echo | None:
        """Claude was audible: check a reply against its last words, else against its sentences."""
        replied_to = self._speech.replied_to_text(heard_at)
        if replied_to and is_echo_of_ending(transcript, replied_to):
            return self._echo(replied_to, heard_at)
        # A reply in Claude's own words is still a reply. But a stop or a wake
        # phrase gets the loose check too: a false stop costs far more than one
        # the user has to repeat.
        if replied_to and not self._has_command(transcript):
            return None
        near = self._speech.text_near(heard_at, heard_until, self._echo_lag_s)
        if is_echo_during_speech(transcript, near):
            return self._echo(near, heard_at)
        return None

    def _has_command(self, transcript: str) -> bool:
        """Whether a transcript holds a wake phrase or is a stop command."""
        return match_wake(transcript, self._wake_phrases) is not None or is_stop_command(transcript)

    def _echo(self, compared_with: str, heard_at: float) -> Echo:
        """An Echo that says what it matched and when it began, for the log."""
        stopped_at = self._speech.audio_stopped_before(heard_at)
        started_after_s = None if stopped_at is None else heard_at - stopped_at
        return Echo(compared_with, started_after_s)
