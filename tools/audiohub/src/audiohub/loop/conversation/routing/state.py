"""The conversation state machine: what phase the loop is in, and what a transcript means.

Pure logic with no I/O, so it is easy to test. `ConversationState.route`
turns each transcript into a route (`Ask`, `Attend`, `Cancel`,
`Echo`, `Ignore` or `BargeIn`; routes.py says what each means). An `Ask`
needs a wake phrase, the follow-up window, or `wake.require_wake` off.

The follow-up window opens once Claude's audio ends (or after a bare wake
phrase) and closes as soon as a request is accepted, or a stop or barge-in
cuts Claude off, so side chatter during the next turn doesn't reach the brain.
A window opened by an audio end starts there: chatter begun while it was
shut, say while Claude was thinking, stays outside it however late Whisper
routes it.

Echoes are dropped first (echo_check.py). With barge-in on, an utterance
begun while Claude was still audible to the user (before `reply_after_s`
past its audio end, and before any barge-in cut it) then follows the
talk-over rules: a stop needs no wake phrase, anything else needs one whatever
`wake.require_wake` says. With barge-in off,
routing ignores timing, apart from the follow-up window.
"""

import math

from audiohub.config import WakeSettings

from ...phrases import is_stop_command, match_wake
from .echo_check import EchoCheck
from .routes import Ask, Attend, BargeIn, Cancel, Ignore, Phase, Route
from .speech_window import SpeechHistory


class ConversationState:
    """Tracks brain turns, speech and the follow-up window, and routes transcripts.

    Times are `time.monotonic()` seconds, passed in so tests control them.
    """

    def __init__(
        self,
        wake_settings: WakeSettings,
        *,
        is_barge_in: bool = False,
        echo_lag_s: float = 0.0,
        reply_after_s: float = 0.0,
    ) -> None:
        """Start in the listening phase with no follow-up window open.

        Args:
            wake_settings: Wake phrases, whether one is required, follow-up length.
            is_barge_in: Whether the mic stays live while Claude speaks, so
                utterances heard then get the talk-over rules. False is
                half-duplex: the mic is muted then, and routing ignores timing.
            echo_lag_s: How long a sentence may still reach the mic after it
                stopped playing (the output lag, `audio.echo_tail_s`).
            reply_after_s: How long after Claude's audio ends the user hears
                it end (`audio.reply_after_s`), capped at `echo_lag_s`: past
                the echo tail nothing of Claude's is left to hear.
        """
        self._wake = wake_settings
        self._is_barge_in = is_barge_in
        self._echo_lag_s = echo_lag_s
        self._reply_after_s = min(reply_after_s, echo_lag_s)
        self._open_turns = 0
        self._is_speaking = False
        # The follow-up window: [from, until], or shut while until is None.
        self._follow_up_from = -math.inf
        self._follow_up_until: float | None = None
        # The window the last audio end replaced, as (from, until), still
        # checked for replies begun in it but routed after that audio end.
        self._replaced_follow_up: tuple[float, float | None] = (-math.inf, None)
        self._speech = SpeechHistory()
        self._echoes = EchoCheck(
            self._speech, wake_settings.phrases, is_barge_in=is_barge_in, echo_lag_s=echo_lag_s
        )

    @property
    def phase(self) -> Phase:
        """Speaking beats thinking beats listening."""
        if self._is_speaking:
            return Phase.SPEAKING
        if self._open_turns:
            return Phase.THINKING
        return Phase.LISTENING

    def turn_started(self) -> None:
        """A request went to the brain. Closes the follow-up window."""
        self._open_turns += 1
        self.close_follow_up()

    def turn_finished(self) -> None:
        """The brain finished (or abandoned) a request."""
        self._open_turns = max(0, self._open_turns - 1)

    def speech_started(self) -> None:
        """The hub started speaking to the user (a new batch)."""
        self._is_speaking = True
        self._speech.start_batch()

    def sentence_started(self, now: float, text: str) -> None:
        """A sentence chunk of the current batch started playing at `now`."""
        self._speech.current.sentence_started(now, text)

    def speech_interrupted(self, now: float, heard_until: float) -> None:
        """A barge-in cut the current speech at `now`, by an utterance that ended at `heard_until`.

        Utterances from after `heard_until` are routed normally again (but
        still echo-checked until `speech_finished`). The follow-up window
        closes, one left open from an earlier batch included, and the end of
        this speech won't reopen it; a bare "Hey Claude" (Attend) does.
        """
        self._speech.current.interrupt(now, heard_until)
        self.close_follow_up()

    def speech_audio_ended(self, now: float, *, is_cut: bool = False) -> None:
        """The current batch stopped playing here at `now`; its echo tail starts.

        Unless it was cut, Claude has said everything, so once the user hears
        it end (`reply_after_s` from now) they may reply without a wake
        phrase. Until then they are still talking over Claude, so the
        follow-up window is set now and lasts `follow_up_s` past the echo tail
        (with `follow_up_s` 0 there is none, and every reply needs the wake phrase).
        It starts now, unless a window was still open: then that one goes on.
        Either way a reply begun in the earlier window but routed after this
        audio end still counts.

        Args:
            now: When the audio ended.
            is_cut: Whether a stop cut it short rather than it playing out. A
                cut batch is treated like one a barge-in cut: no replies to
                it, and no follow-up window.
        """
        window = self._speech.current
        if is_cut:
            window.interrupt(now, heard_until=now)
        window.audio_ended(now, self._reply_after_s)
        if window.is_interrupted or self._wake.follow_up_s <= 0:
            return
        if not self.is_in_follow_up(now):
            self._replaced_follow_up = (self._follow_up_from, self._follow_up_until)
            self._follow_up_from = now
        self._follow_up_until = now + self._echo_lag_s + self._wake.follow_up_s

    def speech_finished(self, now: float, spoken_text: str = "") -> None:
        """The hub stopped speaking: the audio and its echo tail are over.

        Args:
            now: When the echo tail ended (and, half-duplex, the mic reopened).
            spoken_text: What was just said, to recognise its echo.
        """
        window = self._speech.current
        if not window.is_interrupted and window.audio_ended_at is None:
            # Its audio end was never reported (no echo tail): reply from now on.
            self.open_follow_up(now)
        self._is_speaking = False
        self._echoes.speech_finished(now, spoken_text)
        window.finish(now)

    def open_follow_up(self, now: float) -> None:
        """Accept requests without a wake phrase for `follow_up_s` from `now`.

        The window has no start, so a request begun just before it opened (the
        one right after a bare "Hey Claude") counts too.
        """
        self._follow_up_from = -math.inf
        self._follow_up_until = now + self._wake.follow_up_s

    def close_follow_up(self) -> None:
        """Require a wake phrase again (a request was accepted)."""
        self._follow_up_until = None
        self._replaced_follow_up = (-math.inf, None)

    def is_in_follow_up(self, at: float) -> bool:
        """Say whether time `at` falls inside the follow-up window (or the one it replaced)."""
        windows = ((self._follow_up_from, self._follow_up_until), self._replaced_follow_up)
        return any(until is not None and start <= at <= until for start, until in windows)

    def tail_offset(self, heard_at: float) -> float | None:
        """How long after Claude's audio ended an utterance begun at `heard_at` began.

        For the log, to tune `reply_after_s` from what was accepted as well
        as from what was dropped as echo.

        Returns:
            The offset in seconds, or None unless it began in the echo tail of
            a batch that played out.
        """
        return self._speech.tail_offset(heard_at)

    def route(
        self,
        transcript: str,
        heard_at: float,
        *,
        heard_until: float | None = None,
    ) -> Route:
        """Decide what one transcript means. Does not change the state.

        Args:
            transcript: What the user said.
            heard_at: When they started saying it (for the follow-up window).
            heard_until: When they finished; None means `heard_at`.

        Returns:
            The route to follow (see the module docstring).
        """
        heard_until = heard_at if heard_until is None else heard_until
        echo = self._echoes.find(transcript, heard_at, heard_until)
        if echo is not None:
            return echo
        if self._is_barge_in and self._speech.is_talked_over(heard_at, heard_until):
            route = self._route_talk_over(transcript)
            return route if isinstance(route, Ignore) else BargeIn(route)
        return self._route_request(transcript, heard_at)

    def _route_request(self, transcript: str, heard_at: float) -> Route:
        request = match_wake(transcript, self._wake.phrases)
        has_wake_phrase = request is not None
        if request is None:
            if self._wake.require_wake and not self.is_in_follow_up(heard_at):
                return Ignore()
            request = transcript.strip()
        if is_stop_command(request):
            return Cancel()
        if not request:
            return Attend()
        return Ask(request, has_wake_phrase)

    def _route_talk_over(self, transcript: str) -> Ask | Attend | Cancel | Ignore:
        """Claude is audible: only a stop (bare or after a wake phrase) or a wake phrase counts."""
        request = match_wake(transcript, self._wake.phrases)
        if is_stop_command(transcript if request is None else request):
            return Cancel()
        if request is None:
            return Ignore()
        return Ask(request, has_wake_phrase=True) if request else Attend()
