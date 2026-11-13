"""Shared fakes for loop tests: TTS, speaker, ducker, dispatcher, brain, hearing, music.

Nothing here touches audio devices, models or the network. Test modules can't
import conftest directly, so the fakes are handed out through fixtures.
"""

import asyncio
import contextlib
import dataclasses
import time
from collections.abc import AsyncIterator, Callable
from types import SimpleNamespace

import numpy as np
import pytest

from audiohub.brain import ReplyText, TurnDone
from audiohub.kernel import Decision
from audiohub.loop import Heard, VoiceOutput
from audiohub.music import NowPlaying

TTS_RATE = 24000
DONE = TurnDone(duration_s=1.5, cost_usd=0.002, is_error=False)
TRACK = NowPlaying("Babydoll", "Dominic Fike", "", is_playing=True, source="spotify")


class FakeSynthesizer:
    """Returns a short buffer per chunk and records what it was asked to say."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, str | None]] = []
        self.call_times: list[float] = []
        self.error: Exception | None = None

    def synthesize(self, text: str, voice: str | None = None) -> tuple[np.ndarray, int]:
        self.calls.append((text, voice))
        self.call_times.append(time.monotonic())
        if self.error is not None:
            raise self.error
        return np.full(len(text), 0.1, dtype=np.float32), TTS_RATE


class FakeSpeaker:
    """Pretends to play each buffer for `play_s` seconds; `stop()` ends it early."""

    def __init__(self) -> None:
        self.played: list[int] = []
        # (start, end) monotonic times of each play call.
        self.play_spans: list[tuple[float, float]] = []
        self.play_s = 0.01
        self.stop_count = 0
        # Raised by the next play() call, once (like a stalled Bluetooth device).
        self.next_error: Exception | None = None
        self.on_play: Callable[[], None] | None = None
        self._stopped = asyncio.Event()

    async def play(self, samples: np.ndarray, sample_rate: int) -> None:
        if self.next_error is not None:
            error, self.next_error = self.next_error, None
            raise error
        self.played.append(len(samples))
        if self.on_play is not None:
            self.on_play()
        self._stopped.clear()
        started = time.monotonic()
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(self._stopped.wait(), self.play_s)
        self.play_spans.append((started, time.monotonic()))

    def stop(self) -> None:
        self.stop_count += 1
        self._stopped.set()


class FakeDucker:
    """Records duck/restore calls in order."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    @property
    def is_ducked(self) -> bool:
        return bool(self.calls) and self.calls[-1] == "duck"

    def duck(self) -> None:
        self.calls.append("duck")

    def restore(self) -> None:
        self.calls.append("restore")


class FakeDispatcher:
    """Delivers every pending message verbatim, except the ids in `hold_ids`."""

    def __init__(self) -> None:
        self.hold_ids: set[str] = set()
        self.started = self.closed = False

    async def start(self) -> None:
        self.started = True

    async def close(self) -> None:
        self.closed = True

    async def decide(self, pending, recent_delivered) -> list[Decision]:
        return [
            Decision(m.id, "hold" if m.id in self.hold_ids else "deliver", None, "test")
            for m in pending
        ]


class FakeBrain:
    """A VoiceBrain whose replies come from `script(request, brain)`, an async generator."""

    def __init__(self, script=None) -> None:
        self.script = script or _echo_script
        self.requests: list[str] = []
        self.interrupt_count = 0
        self.started = self.closed = False

    async def start(self) -> None:
        self.started = True

    async def close(self) -> None:
        self.closed = True

    async def ask(self, text: str) -> AsyncIterator[ReplyText | TurnDone]:
        self.requests.append(text)
        async for event in self.script(text, self):
            yield event

    async def interrupt(self) -> None:
        self.interrupt_count += 1


async def _echo_script(request: str, brain: FakeBrain) -> AsyncIterator[ReplyText | TurnDone]:
    yield ReplyText(f"You said: {request}")
    yield DONE


# How long each fake utterance lasts.
HEARD_AUDIO_S = 1.0


class FakeHearing:
    """Stands in for Hearing: tests push transcripts with `hear(text)`.

    Like the real Hearing, an utterance heard now is stamped as having ended
    now, so it started HEARD_AUDIO_S ago.
    """

    def __init__(self) -> None:
        self._queue: asyncio.Queue[Heard] = asyncio.Queue()
        self.paused = False
        self.pause_count = 0
        self.loaded = self.opened = self.closed = False
        self.device_in_use, self.model_in_use = "cpu", "fake-whisper"

    def hear(self, text: str, started_at: float | None = None) -> None:
        heard_at = time.monotonic() - HEARD_AUDIO_S if started_at is None else started_at
        self._queue.put_nowait(Heard(text, heard_at, HEARD_AUDIO_S, 0.05))

    async def load(self) -> None:
        self.loaded = True

    async def __aenter__(self) -> "FakeHearing":
        self.opened = True
        return self

    async def __aexit__(self, *exc_info) -> None:
        self.closed = True

    async def utterances(self) -> AsyncIterator[Heard]:
        while True:
            yield await self._queue.get()

    def pause(self) -> None:
        self.paused = True
        self.pause_count += 1

    def resume(self) -> None:
        self.paused = False

    async def wait_until_quiet(self, timeout_s: float) -> bool:
        return True


class FakeMusic:
    """A MusicController's play/pause/now_playing: pause and play flip `track.is_playing`.

    `calls` records (method, clock()) in order. A method named in `failures`
    raises that error, and one in `hangs` never returns (a dead backend).
    """

    def __init__(self, track: NowPlaying | None = TRACK, clock=time.monotonic) -> None:
        self.track = track
        self.clock = clock
        self.calls: list[tuple[str, float]] = []
        self.failures: dict[str, Exception] = {}
        self.hangs: set[str] = set()

    @property
    def names(self) -> list[str]:
        return [name for name, _ in self.calls]

    def time_of(self, name: str) -> float:
        return next(at for called, at in self.calls if called == name)

    async def now_playing(self) -> NowPlaying | None:
        await self._record("now_playing")
        return self.track

    async def pause(self) -> None:
        await self._record("pause")
        self.track = dataclasses.replace(self.track, is_playing=False)

    async def play(self) -> None:
        await self._record("play")
        self.track = dataclasses.replace(self.track, is_playing=True)

    async def _record(self, name: str) -> None:
        self.calls.append((name, self.clock()))
        if name in self.hangs:
            await asyncio.Event().wait()
        if name in self.failures:
            raise self.failures[name]


async def wait_until(predicate: Callable[[], bool], timeout_s: float = 3.0) -> None:
    """Poll until `predicate()` is true, failing the test after `timeout_s`."""
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout_s
    while not predicate():
        if loop.time() > deadline:
            raise AssertionError("condition not met in time")
        await asyncio.sleep(0.005)


@pytest.fixture
def fakes() -> SimpleNamespace:
    """The fake classes and helpers, for tests that build their own."""
    return SimpleNamespace(
        Synthesizer=FakeSynthesizer,
        Speaker=FakeSpeaker,
        Ducker=FakeDucker,
        Dispatcher=FakeDispatcher,
        Brain=FakeBrain,
        Hearing=FakeHearing,
        Music=FakeMusic,
        DONE=DONE,
        TRACK=TRACK,
        wait_until=wait_until,
    )


@pytest.fixture
def synthesizer() -> FakeSynthesizer:
    return FakeSynthesizer()


@pytest.fixture
def speaker() -> FakeSpeaker:
    return FakeSpeaker()


@pytest.fixture
def ducker() -> FakeDucker:
    return FakeDucker()


@pytest.fixture
def voice(synthesizer, speaker, ducker) -> VoiceOutput:
    return VoiceOutput(synthesizer, speaker, ducker)
