"""The `make_hub` fixture: a whole Conversation wired to the loop fakes, for end-to-end tests.

Kernel, KernelServer and VoiceOutput are real; the brain, hearing, TTS,
speaker, ducker and Sonnet dispatcher are the fakes from tests/loop/conftest.py,
so nothing touches audio devices, models or the network.
"""

import asyncio
import io

import pytest

from audiohub.config import AudioSettings, Settings
from audiohub.kernel import Kernel, KernelServer
from audiohub.loop import (
    Conversation,
    ConversationParts,
    MusicPause,
    StatusLine,
    VoiceOutput,
)
from audiohub.loop.voice_output import WARM_UP_TEXT

HOST = "127.0.0.1"
ECHO_TAIL_S = 0.02
# [audio] settings of a test hub; make_hub's keyword options override them.
AUDIO_DEFAULTS = {"barge_in": False, "echo_tail_s": ECHO_TAIL_S, "wake_chime": False}


class Hub:
    """A Conversation wired to fakes, run as a background task by `async with`.

    `music`, a FakeMusic, turns the music pause on, resuming with no grace.
    `record_path` makes the hub write its pid record there (none by default).
    """

    def __init__(
        self,
        fakes,
        tmp_path,
        brain=None,
        *,
        listen: bool = True,
        port: int = 0,
        music=None,
        record_path=None,
        **audio_options,
    ) -> None:
        self.fakes = fakes
        audio = AUDIO_DEFAULTS | audio_options
        self.settings = Settings(audio=AudioSettings(**audio))
        self.status_stream = io.StringIO()
        status = StatusLine(self.status_stream)
        self.dispatcher = fakes.Dispatcher()
        kernel = Kernel(self.settings.kernel, dispatcher=self.dispatcher)
        self.synthesizer, self.speaker, self.ducker = (
            fakes.Synthesizer(),
            fakes.Speaker(),
            fakes.Ducker(),
        )
        voice = VoiceOutput(self.synthesizer, self.speaker, self.ducker)
        self.hearing = fakes.Hearing() if listen else None
        self.brain = (brain or fakes.Brain()) if listen else None
        # Its own token file, so a test never overwrites the live hub's .cache/ipc-token.
        self.token_path = tmp_path / "ipc-token"
        server = KernelServer(kernel, HOST, port, self.token_path)
        music_pause = MusicPause(music, resume_after_s=0.0) if music is not None else None
        self.parts = ConversationParts(
            kernel,
            server,
            voice,
            status,
            self.hearing,
            self.brain,
            music_pause,
            record_path,
        )
        self.conversation = Conversation(self.settings, listen, self.parts)
        self.mic_paused_during_play: list[bool] = []
        if self.hearing is not None:
            self.speaker.on_play = lambda: self.mic_paused_during_play.append(self.hearing.paused)

    @property
    def spoken(self) -> str:
        """Everything synthesized after the warm-up, joined."""
        return " ".join(text for text, _ in self.synthesizer.calls if text != WARM_UP_TEXT)

    @property
    def status_text(self) -> str:
        return self.status_stream.getvalue()

    async def __aenter__(self) -> "Hub":
        self.task = asyncio.create_task(self.conversation.run())
        await self.fakes.wait_until(lambda: "] ready" in self.status_text or self.task.done())
        return self

    async def __aexit__(self, *exc_info) -> None:
        self.task.cancel()
        await asyncio.gather(self.task, return_exceptions=True)


@pytest.fixture
def make_hub(fakes, tmp_path):
    """Build a Hub: `make_hub(brain=None, *, listen=True, port=0, music=None, record_path=None,
    **audio_options)`.

    `audio_options` override AUDIO_DEFAULTS, e.g. `barge_in=True`. Barge-in
    and the wake chime default to off here: most tests cover flows they don't
    change, and half-duplex keeps their timing simple. test_barge_in.py turns
    barge-in on, test_wake_chime.py the chime.
    """

    def make(brain=None, **options) -> Hub:
        return Hub(fakes, tmp_path, brain, **options)

    return make
