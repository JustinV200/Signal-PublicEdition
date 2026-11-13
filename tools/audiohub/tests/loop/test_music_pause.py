"""Tests for MusicPause: music paused for a conversation, resumed after it, left alone otherwise.

A fake clock drives the polls (each sleep moves it on), so the grace period is
checked in fake seconds; the hub's activity is two flags the test flips.
"""

import asyncio
import contextlib
import logging
from types import SimpleNamespace

import pytest

from audiohub.loop import MusicPause
from audiohub.loop import music_pause as music_pause_module
from audiohub.music import MusicUnavailable, NowPlaying, UnavailableReason

GRACE_S = 2.0


class FakeClock:
    """Monotonic seconds that move only when the music pause sleeps."""

    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now

    async def sleep(self, seconds: float) -> None:
        self.now += seconds
        await asyncio.sleep(0)


class FakeHub:
    """A HubActivity: `busy` while Claude thinks or speaks, `open` for the follow-up window."""

    def __init__(self) -> None:
        self.busy = False
        self.open = False

    def is_busy(self) -> bool:
        return self.busy

    def is_conversation_open(self) -> bool:
        return self.open


@pytest.fixture
def rig(fakes) -> SimpleNamespace:
    clock = FakeClock()
    music = fakes.Music(clock=clock)
    pause = MusicPause(music, GRACE_S, sleep=clock.sleep)
    return SimpleNamespace(clock=clock, music=music, hub=FakeHub(), pause=pause, fakes=fakes)


@contextlib.asynccontextmanager
async def running(rig: SimpleNamespace):
    task = asyncio.create_task(rig.pause.run(rig.hub))
    try:
        yield task
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)


async def end_conversation(rig: SimpleNamespace) -> None:
    """Make the hub idle, then wait until the grace period is long over."""
    rig.hub.busy = rig.hub.open = False
    over_at = rig.clock.now + GRACE_S + 1.0
    await rig.fakes.wait_until(lambda: rig.clock.now > over_at)


@pytest.mark.asyncio
@pytest.mark.parametrize("is_woken", [True, False], ids=["wake", "notification"])
async def test_music_paused_for_claude_resumes_once_the_conversation_is_over(rig, is_woken):
    rig.hub.busy = True  # Claude is thinking or speaking
    async with running(rig):
        if is_woken:
            rig.pause.hold()
        await rig.fakes.wait_until(lambda: "pause" in rig.music.names)
        rig.hub.busy, rig.hub.open = False, True  # Claude is done; the follow-up window is open
        if is_woken:
            # After a wake the open window keeps the music paused, however long it lasts.
            await asyncio.sleep(0.05)
            assert "play" not in rig.music.names
            rig.hub.open = False
        ended_at = rig.clock.now
        await rig.fakes.wait_until(lambda: "play" in rig.music.names)
    assert rig.music.names == ["now_playing", "pause", "now_playing", "play"]
    assert rig.music.time_of("play") - ended_at == pytest.approx(GRACE_S)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "track",
    [None, NowPlaying("Babydoll", "Dominic Fike", "", is_playing=False, source="spotify")],
    ids=["nothing loaded", "paused"],
)
async def test_music_that_was_not_playing_is_never_paused_or_started(rig, track):
    rig.music.track = track
    rig.hub.busy = True
    async with running(rig):
        rig.pause.hold()
        await rig.fakes.wait_until(lambda: "now_playing" in rig.music.names)
        # The user starts the music mid-conversation and says "Hey Claude" again.
        rig.music.track = rig.fakes.TRACK
        rig.pause.hold()
        await end_conversation(rig)
    assert rig.music.names == ["now_playing"]


def user_plays_it(rig: SimpleNamespace) -> None:
    rig.music.track = rig.fakes.TRACK


def claude_pauses_it(rig: SimpleNamespace) -> None:
    rig.pause.note_tool_call("mcp__audiohub__music_pause")


def another_track_is_loaded(rig: SimpleNamespace) -> None:
    rig.music.track = NowPlaying("Clip", "Someone", "", False, "smtc:MSEdge")


def claude_skips_it(rig: SimpleNamespace) -> None:
    rig.pause.note_tool_call("mcp__audiohub__music_next")
    rig.music.track = NowPlaying("Next song", "Someone", "", False, "spotify")


async def converse(rig: SimpleNamespace, change=None) -> None:
    """One conversation: a wake pauses the music, `change` happens, then it ends."""
    rig.hub.busy = True
    rig.pause.hold()
    await rig.fakes.wait_until(lambda: "pause" in rig.music.names)
    if change is not None:
        change(rig)
    rig.pause.hold()  # another wake in the same conversation never pauses again
    await end_conversation(rig)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("change", "is_resumed"),
    [
        (user_plays_it, False),
        (claude_pauses_it, False),
        (another_track_is_loaded, False),
        (claude_skips_it, True),  # the skipped-to track plays, not silence
    ],
)
async def test_music_changed_during_the_conversation_is_left_alone_unless_skipped(
    rig, change, is_resumed
):
    async with running(rig):
        await converse(rig, change)
        assert rig.music.names.count("pause") == 1
        assert ("play" in rig.music.names) is is_resumed
        # The next conversation starts afresh: what happened in this one doesn't stick.
        rig.music.track, rig.music.calls = rig.fakes.TRACK, []
        await converse(rig)
    assert rig.music.names == ["now_playing", "pause", "now_playing", "play"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("method", "failure"),
    [
        ("now_playing", MusicUnavailable("Open Spotify.", UnavailableReason.NO_ACTIVE_DEVICE)),
        ("pause", RuntimeError("winrt fell over")),
        ("pause", None),  # never answers
    ],
    ids=["unavailable", "crash", "hang"],
)
async def test_a_failing_music_backend_is_logged_and_never_resumed(
    rig, monkeypatch, caplog, method, failure
):
    monkeypatch.setattr(music_pause_module, "MUSIC_CALL_TIMEOUT_S", 0.01)
    caplog.set_level(logging.INFO, logger=music_pause_module.__name__)
    if failure is None:
        rig.music.hangs.add(method)
    else:
        rig.music.failures[method] = failure
    rig.hub.busy = True
    async with running(rig) as task:
        rig.pause.hold()
        await rig.fakes.wait_until(lambda: "could not pause the music" in caplog.text)
        await end_conversation(rig)
        # A pause that failed (or may land late) is never claimed, so never resumed.
        assert "play" not in rig.music.names
        rig.music.failures.clear()
        rig.music.hangs.clear()
        rig.hub.busy = True
        rig.pause.hold()
        # The next conversation still pauses the music.
        await rig.fakes.wait_until(lambda: not rig.music.track.is_playing)
        assert not task.done()
