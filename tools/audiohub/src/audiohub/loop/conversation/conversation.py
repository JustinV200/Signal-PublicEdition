"""`Conversation`: the whole voice hub, wired together and run until Ctrl+C.

    mic -> Hearing -> route (wake / follow-up / yes-no / stop / barge-in) -> BrainTurns
        -> kernel -> Delivery -> VoiceOutput (music ducked)

With `audio.barge_in` on, the mic stays live while Claude speaks, and a stop
or wake phrase heard over Claude cuts its speech before being followed as
usual. With it off, the mic is paused while Claude speaks (half-duplex).
An accepted wake phrase plays the wake chime (`audio.wake_chime`), and an
accepted request or wake phrase pauses the music until the conversation is
over (`music.pause_on_wake`, see loop/music_pause.py). Every
transcript dropped as an echo is logged with what it matched and when it
began, and so is every other one begun in the echo tail, to tune
`audio.reply_after_s` from both sides.

The KernelServer runs alongside, so other processes can send notifications,
or ask the hub to shut down cleanly (the console's Voice Stop does).
Once its port is bound, the hub records its pid in `.cache/hub.json`
(hub_record.py) for the console's Stop, and removes it again on the way out.
Startup loads Whisper and Kokoro, connects Claude and the kernel's Sonnet
session in parallel. On shutdown everything is closed in reverse order, and
the voice output restores any ducked music.
"""

import asyncio
import contextlib
import logging
import time

from audiohub.config import Settings

from ..chime import WakeChime
from ..status import format_duration, quote
from ..tasks import run_tasks
from .activity import ConversationActivity
from .delivery import Delivery
from .hub_record import record_hub
from .parts import ConversationParts, build_parts
from .routing import (
    Ask,
    Attend,
    BargeIn,
    Cancel,
    ConversationState,
    Echo,
    Ignore,
    Phase,
    Route,
)
from .turns import BrainTurns

logger = logging.getLogger(__name__)

# Longest part of Claude's speech quoted when an echo is dropped (its end is kept).
ECHO_QUOTE_CHARS = 60


class HubStartError(RuntimeError):
    """The hub couldn't start, e.g. because another hub already holds the IPC port."""


class Conversation:
    """The voice hub. `await run()` until cancelled or asked to shut down over IPC."""

    def __init__(
        self, settings: Settings, listen: bool = True, parts: ConversationParts | None = None
    ) -> None:
        """Prepare the hub; nothing starts until `run()`.

        Args:
            settings: The loaded settings.
            listen: False runs a speak-only hub (kernel, IPC and voice output).
            parts: Components to use instead of `build_parts(settings, listen)`.

        Raises:
            ValueError: If `listen` is True but `parts` has no hearing or brain.
        """
        self._settings = settings
        self._parts = parts or build_parts(settings, listen)
        if listen and (self._parts.hearing is None or self._parts.brain is None):
            raise ValueError("a listening Conversation needs parts with hearing and a brain")
        self._listen = listen
        audio = settings.audio
        self._state = ConversationState(
            settings.wake,
            is_barge_in=audio.barge_in,
            echo_lag_s=audio.echo_tail_s,
            reply_after_s=audio.reply_after_s,
        )
        self._delivery = Delivery(
            self._parts, self._state, audio.echo_tail_s, is_barge_in=audio.barge_in
        )
        self._turns = (
            BrainTurns(
                self._parts.brain, self._parts.kernel.submit, self._state, self._parts.status
            )
            if listen
            else None
        )
        is_chiming = listen and audio.wake_chime
        self._chime = WakeChime(self._parts.voice, audio.wake_chime_volume) if is_chiming else None

    async def run(self) -> None:
        """Start everything, run until cancelled (Ctrl+C), asked to shut down or a part fails.

        The microphone opens once here and stays open for the whole run
        (half-duplex mode mutes it with `paused`), because opening the
        glasses' mic switches them to the Hands-Free profile, which takes 1-2 s.

        Raises:
            HubStartError: If the IPC port is taken.
            DeviceNotFoundError: If the configured microphone doesn't exist.
            AudioStreamError: If the microphone can't be opened.
            RuntimeError: If no Whisper model can be loaded.
        """
        async with contextlib.AsyncExitStack() as stack:
            await self._start(stack)
            # A shutdown request over IPC ends the run like Ctrl+C, so the
            # stack below restores the music and closes everything.
            loops = [self._delivery.run(), self._parts.server.wait_for_shutdown()]
            if self._turns is not None:
                loops += [self._turns.run(), self._hear()]
            if self._chime is not None:
                loops.append(self._chime.run())
            if self._parts.music_pause is not None:
                activity = ConversationActivity(self._state, self._parts.kernel)
                loops.append(self._parts.music_pause.run(activity))
            try:
                await run_tasks(loops, asyncio.FIRST_COMPLETED)
            finally:
                self._parts.status.show("stopping")

    async def _start(self, stack: contextlib.AsyncExitStack) -> None:
        parts = self._parts
        parts.status.show("starting", "loading models and connecting to Claude")
        started = time.monotonic()
        # Close callbacks go on the stack before starting, so a failed start
        # still releases whatever did connect.
        stack.push_async_callback(parts.kernel.close)
        stack.callback(parts.voice.close)
        startups = [parts.kernel.start(), parts.voice.warm_up()]
        if self._listen:
            stack.push_async_callback(parts.brain.close)
            startups += [parts.hearing.load(), parts.brain.start()]
        await run_tasks(startups, asyncio.FIRST_EXCEPTION)
        await self._start_server(stack)
        record_hub(stack, parts.record_path)  # only now that the IPC port is bound
        if self._listen:
            await stack.enter_async_context(parts.hearing)
        parts.status.show(
            "ready",
            f"{self._describe_setup()} (started in {format_duration(time.monotonic() - started)})",
        )
        parts.status.show(Phase.LISTENING.value if self._listen else "speak-only")

    async def _start_server(self, stack: contextlib.AsyncExitStack) -> None:
        ipc = self._settings.ipc
        try:
            await stack.enter_async_context(self._parts.server)
        except OSError as error:
            raise HubStartError(
                f"can't listen for notifications on {ipc.host}:{ipc.port} ({error}); "
                "is another audiohub already running?"
            ) from error

    def _describe_setup(self) -> str:
        details = [f"voice {self._settings.tts.voice}", f"notify port {self._parts.server.port}"]
        hearing = self._parts.hearing
        if self._listen and hearing is not None:
            details.insert(0, f"stt {hearing.model_in_use} on {hearing.device_in_use}")
        return ", ".join(details)

    async def _hear(self) -> None:
        parts = self._parts
        async for heard in parts.hearing.utterances():
            parts.status.show("heard", heard.describe())
            heard_until = heard.started_at + heard.audio_s
            route = self._state.route(
                heard.text,
                heard.started_at,
                heard_until=heard_until,
            )
            self._log_tail_utterance(route, heard.text, heard.started_at)
            if isinstance(route, BargeIn):
                self._barge_in(route.then, heard_until)
                route = route.then
            await self._follow(route, heard.text)

    async def _follow(self, route: Route, transcript: str) -> None:
        status = self._parts.status
        match route:
            case Ask(request, has_wake_phrase):
                if has_wake_phrase:
                    self._play_chime()
                self._hold_music()
                # One accepted request closes the window, so chatter while
                # Claude thinks needs a wake phrase again.
                self._state.close_follow_up()
                self._turns.add(request)
            case Attend():
                self._play_chime()
                self._hold_music()
                self._state.open_follow_up(time.monotonic())
                status.show(Phase.LISTENING.value, "go ahead")
            case Cancel():
                await self._cancel()
            case Echo():
                said, timing = describe_echo(route)
                logger.info(
                    "dropped as echo: heard %s; Claude said %s; %s", quote(transcript), said, timing
                )
                status.show("ignored", f"echo of Claude saying {said} ({timing})")
            case Ignore():
                status.show("ignored", "no wake phrase")

    def _log_tail_utterance(self, route: Route, transcript: str, heard_at: float) -> None:
        """Log what an utterance begun in the echo tail was routed as (echoes are logged later)."""
        offset_s = self._state.tail_offset(heard_at)
        if offset_s is None or isinstance(route, Echo):
            return
        logger.info(
            "heard in the echo tail: %s; %s; routed as %s",
            quote(transcript),
            describe_timing(offset_s),
            type(route).__name__,
        )

    def _barge_in(self, then: Ask | Attend | Cancel, heard_until: float) -> None:
        """The user cut in over Claude: stop its speech now, and drop the rest of the batch.

        A new request (not a stop, which `_cancel` handles in full) also makes
        Claude's other unspoken replies stale.

        Args:
            then: What the user said: Ask, Attend or Cancel.
            heard_until: When the barge-in utterance ended. What the user says
                after it is no longer said over Claude.
        """
        self._delivery.stop()
        self._state.speech_interrupted(time.monotonic(), heard_until)
        if not isinstance(then, Cancel):
            self._delivery.skip_unspoken_replies(before=time.time())
        self._parts.status.show("barge-in", "cut Claude off")

    def _play_chime(self) -> None:
        if self._chime is not None:
            self._chime.request()

    def _hold_music(self) -> None:
        # Returns at once: the music calls run in the music pause's own task.
        if self._parts.music_pause is not None:
            self._parts.music_pause.hold()

    async def _cancel(self) -> None:
        """Handle "Claude, stop": silence Claude and interrupt the turn.

        It also closes the follow-up window: after a stop, chatter needs the
        wake phrase again.
        """
        self._state.close_follow_up()
        self._delivery.skip_unspoken_claude_messages(before=time.time())
        self._delivery.stop()
        await self._turns.cancel()
        self._parts.status.show("cancelled")


def describe_echo(echo: Echo) -> tuple[str, str]:
    """What a dropped echo matched and when it began, for the log and status line.

    Returns:
        The quoted end of Claude's text it matched, and its timing, e.g.
        ('"...should I do it?"', "began 400 ms after Claude's audio ended").
    """
    said = quote(echo.compared_with, ECHO_QUOTE_CHARS, keep_end=True)
    return said, describe_timing(echo.started_after_audio_s)


def describe_timing(offset_s: float | None) -> str:
    """When an utterance began, given its offset from the end of Claude's audio (None: during it).

    Returns:
        E.g. "began 400 ms after Claude's audio ended".
    """
    if offset_s is None:
        return "began while Claude was still playing"
    side = "after" if offset_s >= 0 else "before"
    return f"began {format_duration(abs(offset_s))} {side} Claude's audio ended"
