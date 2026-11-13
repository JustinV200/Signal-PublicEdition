"""`Delivery`: the output loop. Kernel batches are spoken one at a time.

It asks the kernel for its next batch whenever a message arrives, when held
messages are due for a re-check, or when the output goes idle with messages
still pending. Before asking, it waits for a gap in the user's speech, so
Claude doesn't talk over them. Other agents' messages that a cut batch never
reached go back to the kernel and are spoken next: the cut was aimed at
Claude. Each batch counts as speech until
`audio.echo_tail_s` after it ends, because Bluetooth output lags. With
barge-in off, hearing is paused for all that time (half-duplex) so the
glasses mic doesn't hear Claude. With barge-in on, the mic stays live and the
state is told which sentence starts when, and when the audio ended (or was
cut), so it can route what the mic hears meanwhile (talk-over rules, echo
check).
"""

import asyncio
import logging
import time

from audiohub.kernel import OutboundMessage

from ..status import format_duration, quote
from ..voice_output import speakable_chunks
from .outbox import CLAUDE_SOURCE
from .parts import ConversationParts
from .routing import ConversationState

logger = logging.getLogger(__name__)

# Longest wait for the user to finish an utterance before speaking anyway.
USER_QUIET_TIMEOUT_S = 10.0

# Longest text on a status line per spoken message: the console's voice feed
# is the only readable record of what was said, so it gets the full text.
MAX_SAID_CHARS = 2000

Batch = list[tuple[OutboundMessage, str]]


class Delivery:
    """Speaks what the kernel hands out. Run `run()` as a task."""

    def __init__(
        self,
        parts: ConversationParts,
        state: ConversationState,
        echo_tail_s: float,
        *,
        is_barge_in: bool = False,
    ) -> None:
        """Wire the loop to the hub's kernel, voice and hearing.

        Args:
            parts: The hub components (hearing may be None for a speak-only hub).
            state: Told when speech and each sentence start, when the audio
                and then the echo tail end, and what was said.
            echo_tail_s: How long speech lasts after the audio ends (output lag).
            is_barge_in: Keep the mic live while speaking instead of pausing it.
        """
        self._kernel = parts.kernel
        self._voice = parts.voice
        self._hearing = parts.hearing
        self._status = parts.status
        self._state = state
        self._echo_tail_s = echo_tail_s
        self._is_muting_mic = parts.hearing is not None and not is_barge_in
        # Claude's messages created up to this wall-clock time are never spoken.
        self._skip_claude_until: float | None = None
        # Likewise for Claude's direct replies only (a request barge-in).
        self._skip_replies_until: float | None = None
        # Progress of the batch being spoken, to tell what a cut never reached.
        self._sentences_started = 0
        self._was_cut = False

    def stop(self) -> None:
        """Cut off whatever is being spoken, and drop the rest of its batch."""
        if self._voice.speaking:
            self._was_cut = True
        self._voice.stop()

    def skip_unspoken_claude_messages(self, before: float) -> None:
        """Never speak Claude's messages created up to `before` (a `time.time()` value)."""
        self._skip_claude_until = before

    def skip_unspoken_replies(self, before: float) -> None:
        """Never speak Claude's direct replies created up to `before` (a `time.time()` value).

        For a request barge-in, which makes them stale.
        """
        self._skip_replies_until = before

    async def run(self) -> None:
        """Speak kernel batches forever (until cancelled)."""
        should_wait = True
        while True:
            if should_wait:
                await self._wait_for_work()
            if self._hearing is not None:
                await self._hearing.wait_until_quiet(USER_QUIET_TIMEOUT_S)
            decide_started = time.monotonic()
            batch = self._without_skipped(await self._kernel.next_batch())
            if batch:
                await self._speak(batch, time.monotonic() - decide_started)
            # After speaking, messages still pending (held or put back after a
            # cut) are re-decided straight away: the output has just gone idle.
            should_wait = not (batch and self._kernel.pending_count)

    async def _wait_for_work(self) -> None:
        """Wait for kernel work."""
        await self._kernel.wait_for_work()

    def _without_skipped(self, batch: Batch) -> Batch:
        kept = []
        for message, text in batch:
            reason = self._skip_reason(message)
            if reason:
                logger.info("not speaking %s: %s", message.id, reason)
            else:
                kept.append((message, text))
        return kept

    def _skip_reason(self, message: OutboundMessage) -> str | None:
        cutoff = self._skip_claude_until
        if cutoff is not None and message.source == CLAUDE_SOURCE and message.created_at <= cutoff:
            return "the user said stop"
        replies_cutoff = self._skip_replies_until
        # A tie counts as stale: time.time() ticks only every 15.6 ms on Windows
        # (Python 3.12), and the answer to the new request takes far longer.
        is_stale_reply = replies_cutoff is not None and message.created_at <= replies_cutoff
        if message.is_direct_reply and is_stale_reply:
            return "the user cut in with a new request"
        return None

    async def _speak(self, batch: Batch, decide_s: float) -> None:
        # One "speaking" line per message, full text, so the console feed
        # shows everything said; the first carries the kernel's decision time.
        timing = f" (kernel {format_duration(decide_s)})"
        for _, text in batch:
            self._status.show("speaking", f"{quote(text, MAX_SAID_CHARS)}{timing}")
            timing = ""
        self._sentences_started, self._was_cut = 0, False
        await self._speak_and_wait_out_echo(batch)
        if self._was_cut:
            self._requeue_unreached(batch)
        self._status.show(self._state.phase.value)

    async def _speak_and_wait_out_echo(self, batch: Batch) -> None:
        texts = [text for _, text in batch]
        self._state.speech_started()
        if self._is_muting_mic:
            self._hearing.pause()
        try:
            await self._speak_logging_errors(texts)
            self._state.speech_audio_ended(time.monotonic(), is_cut=self._was_cut)
            if self._hearing is not None:
                # Bluetooth output trails the stream by ~1.7 s; wait it out
                # (even after a failure, some audio may still be in flight).
                await asyncio.sleep(self._echo_tail_s)
        finally:
            if self._is_muting_mic:
                self._hearing.resume()
            self._state.speech_finished(time.monotonic(), " ".join(texts))

    def _sentence_started(self, text: str) -> None:
        self._sentences_started += 1
        self._state.sentence_started(time.monotonic(), text)

    def _requeue_unreached(self, batch: Batch) -> None:
        """Give other agents' messages that a cut batch never started back to the kernel.

        Claude's own unreached messages are only logged: the cut was aimed at them.
        """
        sentences_before = 0
        requeued = []
        for message, text in batch:
            if sentences_before >= self._sentences_started:
                logger.warning(
                    "speech was cut before %s from %s: %s", message.id, message.source, quote(text)
                )
                if message.source != CLAUDE_SOURCE:
                    requeued.append(message)
            sentences_before += len(speakable_chunks([text]))
        if requeued:
            self._kernel.requeue(requeued)

    async def _speak_logging_errors(self, texts: list[str]) -> None:
        """Speak the batch, logging (not raising) a failure."""
        try:
            await self._voice.speak_many(texts, on_chunk=self._sentence_started)
        except Exception:
            # Broad on purpose: a lost output device or TTS failure costs this
            # batch only; the hub keeps listening and later messages still try.
            logger.exception("could not speak %d message(s)", len(texts))
