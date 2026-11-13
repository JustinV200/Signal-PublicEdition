"""`SpeechWindow` and `SpeechHistory`: when Claude was audible, and which sentence when.

Barge-in needs both. An utterance that overlaps a window was said over
Claude, so the stricter talk-over routing applies to it, and the sentences
Claude spoke around that time are what an echo of its own voice would repeat.
Pure, with no I/O. Times are `time.monotonic()` seconds passed in by the
caller, and an utterance is the span `[start, end]` it was heard in.

A window covers one spoken batch, from its first sentence starting to
`finish()`, which the delivery loop calls after the echo tail, so the tail
counts as audible. `audio_ended()` marks where the tail starts: the batch has
played out here. The user hears it stop a little later (Bluetooth lags), so
an utterance begun before that still talks over Claude. One begun after it,
in the rest of the tail, is a reply, and only Claude's last words can echo then.
`interrupt()` marks a barge-in: from the end of the barge-in utterance on,
Claude counts as cut off, so new utterances aren't "talking over" it, though
its echo may still arrive until the audio stopped plus the output lag.

`SpeechHistory` keeps the last few windows, because Whisper runs after an
utterance ends: the next batch may already have started by the time the
previous batch's last utterance is routed.
"""

import math
from collections import deque
from dataclasses import dataclass

# Extra slack on the output lag when looking up what Claude said around an
# utterance. Heard.started_at is stamped when the utterance is emitted, so it
# runs late, and a false "stop" costs far more than an ignored one.
ECHO_TIMING_MARGIN_S = 1.0
# Batches kept for routing late utterances; older ones can't overlap anything new.
KEPT_BATCHES = 3


@dataclass(frozen=True)
class _Sentence:
    started_at: float
    text: str


class SpeechWindow:
    """The audible span of one batch of speech and the sentences in it."""

    def __init__(self) -> None:
        """Start empty: nothing has played yet, so nothing overlaps."""
        self._sentences: list[_Sentence] = []
        self._audio_cut_at: float | None = None
        self._audio_ended_at: float | None = None
        self._replies_from: float | None = None
        self._talk_over_until: float | None = None
        self._finished_at: float | None = None

    @property
    def is_interrupted(self) -> bool:
        """Whether a barge-in cut this speech short."""
        return self._audio_cut_at is not None

    @property
    def audio_ended_at(self) -> float | None:
        """When `audio_ended()` reported the batch played out, or None."""
        return self._audio_ended_at

    @property
    def started_at(self) -> float | None:
        """When the first sentence started playing, or None if none has."""
        return self._sentences[0].started_at if self._sentences else None

    @property
    def spoken_text(self) -> str:
        """Every sentence that started playing, joined with spaces."""
        return " ".join(sentence.text for sentence in self._sentences)

    def sentence_started(self, now: float, text: str) -> None:
        """Record that a sentence chunk started playing at `now`."""
        self._sentences.append(_Sentence(now, text))

    def interrupt(self, now: float, heard_until: float) -> None:
        """Record a barge-in. Only the first one counts.

        Args:
            now: When the speech was cut (its audio stopped).
            heard_until: When the barge-in utterance ended. Anything the user
                says after that is no longer said over Claude.
        """
        if self._audio_cut_at is None:
            self._audio_cut_at = now
            self._talk_over_until = heard_until

    def audio_ended(self, now: float, reply_after_s: float = 0.0) -> None:
        """Record that the batch's audio finished playing here at `now` (the echo tail starts).

        Args:
            now: When the audio ended.
            reply_after_s: How long after `now` the user hears it end (the
                output lag). Utterances begun from then on are replies.
        """
        if self._audio_ended_at is None:
            self._audio_ended_at = now
            self._replies_from = now + reply_after_s

    def finish(self, now: float) -> None:
        """Record that the speech and its echo tail ended at `now`."""
        self._finished_at = now

    def audio_stopped_at(self) -> float | None:
        """When the audio stopped (cut or played out), or None while it may still play."""
        for stopped_at in (self._audio_cut_at, self._audio_ended_at, self._finished_at):
            if stopped_at is not None:
                return stopped_at
        return None

    def overlaps(self, start: float, end: float) -> bool:
        """Whether `[start, end]` overlaps the time Claude was audible (echo tail included)."""
        return self._overlaps_until(start, end, self._finished_at)

    def is_talked_over(self, start: float, end: float) -> bool:
        """Whether `[start, end]` overlaps Claude's speech before it was cut off or heard to end.

        An utterance begun once the user heard a played-out batch end is a
        reply (see `is_reply`), not talk-over: Claude has nothing left to say.
        """
        if self.is_interrupted:
            cut_off_at = self._talk_over_until
        else:
            cut_off_at = self._finished_at if self._replies_from is None else self._replies_from
        return self._overlaps_until(start, end, cut_off_at)

    def tail_offset(self, start: float) -> float | None:
        """How long after the audio ended an utterance begun at `start` began, if in the tail.

        Returns:
            The offset in seconds, or None if this batch was cut, its audio
            hasn't ended, or `start` is outside the tail.
        """
        if self.is_interrupted or self._audio_ended_at is None or start < self._audio_ended_at:
            return None
        if self._finished_at is not None and start >= self._finished_at:
            return None
        return start - self._audio_ended_at

    def is_reply(self, start: float) -> bool:
        """Whether an utterance begun at `start` is a reply: in the tail, once the end was heard."""
        return self.tail_offset(start) is not None and start >= self._replies_from

    def text_near(self, start: float, end: float, lag_s: float) -> str:
        """The sentences that could be audible during `[start, end]`.

        Args:
            start: When the utterance began.
            end: When it ended.
            lag_s: How long a sentence may still be heard after the next one
                (or the end of speech) took over, i.e. the output lag.
                ECHO_TIMING_MARGIN_S is added to it.

        Returns:
            Those sentences joined with spaces, or "" when none qualify.
        """
        trail_s = lag_s + ECHO_TIMING_MARGIN_S
        texts = []
        for index, sentence in enumerate(self._sentences):
            if sentence.started_at <= end and self._sentence_end(index) + trail_s >= start:
                texts.append(sentence.text)
        return " ".join(texts)

    def _sentence_end(self, index: int) -> float:
        """When sentence `index` stopped playing: the next one's start, or the audio stopping."""
        if index + 1 < len(self._sentences):
            return self._sentences[index + 1].started_at
        stopped_at = self.audio_stopped_at()
        return math.inf if stopped_at is None else stopped_at

    def _overlaps_until(self, start: float, end: float, until: float | None) -> bool:
        if not self._sentences:
            return False
        return end >= self._sentences[0].started_at and (until is None or start < until)


class SpeechHistory:
    """The current batch's SpeechWindow and the few before it, checked together."""

    def __init__(self) -> None:
        """Start with one empty window, so `current` always exists."""
        self._windows: deque[SpeechWindow] = deque([SpeechWindow()], maxlen=KEPT_BATCHES)

    @property
    def current(self) -> SpeechWindow:
        """The window of the batch being spoken, or of the last one."""
        return self._windows[-1]

    def start_batch(self) -> None:
        """Open a window for a new batch, keeping the last few."""
        self._windows.append(SpeechWindow())

    def overlaps(self, start: float, end: float) -> bool:
        """Whether `[start, end]` overlaps any kept batch while it was audible."""
        return any(window.overlaps(start, end) for window in self._windows)

    def is_talked_over(self, start: float, end: float) -> bool:
        """Whether `[start, end]` was said over any kept batch before it was cut off."""
        return any(window.is_talked_over(start, end) for window in self._windows)

    def replied_to_text(self, start: float) -> str:
        """What Claude said in the batch an utterance begun at `start` replies to, or "" if none."""
        return next((w.spoken_text for w in self._windows if w.is_reply(start)), "")

    def tail_offset(self, start: float) -> float | None:
        """`SpeechWindow.tail_offset` of the kept batch whose tail `start` falls in, or None."""
        offsets = (window.tail_offset(start) for window in self._windows)
        return next((offset for offset in offsets if offset is not None), None)

    def text_near(self, start: float, end: float, lag_s: float) -> str:
        """The sentences of every kept batch that could be audible during `[start, end]`."""
        texts = (window.text_near(start, end, lag_s) for window in self._windows)
        return " ".join(text for text in texts if text)

    def audio_stopped_before(self, start: float) -> float | None:
        """When the last batch begun by `start` stopped playing; None if none or still playing."""
        for window in reversed(self._windows):
            started_at = window.started_at
            if started_at is not None and started_at <= start:
                return window.audio_stopped_at()
        return None
