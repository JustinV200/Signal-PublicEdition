"""Tests for brain-turn failures, background text and merged requests."""

import asyncio
import io

import pytest

from audiohub.config import WakeSettings
from audiohub.loop import StatusLine
from audiohub.loop.conversation import (
    BACKGROUND_SOURCE,
    CLAUDE_SOURCE,
    HUB_SOURCE,
    ConversationState,
)
from audiohub.loop.conversation.turns import (
    DROPPED_SPEECH_TEXT,
    MAX_QUEUED_CHARS,
    BrainTurns,
    background_forwarder,
)


@pytest.mark.asyncio
async def test_a_failed_turn_tells_the_user_and_ends_the_turn(fakes):
    async def broken(request, brain):
        raise ConnectionError("CLI exited")
        yield  # pragma: no cover - makes this an async generator

    submitted = []
    state = ConversationState(WakeSettings())
    turns = BrainTurns(fakes.Brain(broken), submitted.append, state, StatusLine(io.StringIO()))
    worker = asyncio.create_task(turns.run())
    turns.add("what's the time?")
    await fakes.wait_until(lambda: submitted and state.phase.value == "listening")
    worker.cancel()
    assert [(m.source, m.priority) for m in submitted] == [(HUB_SOURCE, "high")]


@pytest.mark.asyncio
async def test_turn_replies_are_direct_replies_from_claude(fakes):
    submitted = []
    state = ConversationState(WakeSettings())
    turns = BrainTurns(fakes.Brain(), submitted.append, state, StatusLine(io.StringIO()))
    worker = asyncio.create_task(turns.run())
    turns.add("hello")
    await fakes.wait_until(lambda: submitted)
    worker.cancel()
    (message,) = submitted
    assert (message.source, message.priority, message.is_direct_reply) == (
        CLAUDE_SOURCE,
        "high",
        True,
    )


def test_background_text_goes_to_the_kernel_at_normal_priority():
    submitted = []
    forward = background_forwarder(submitted.append, StatusLine(io.StringIO()))
    assert forward("The test run finished: all green.") is None
    forward("   ")
    assert [(m.source, m.priority, m.is_direct_reply, m.text) for m in submitted] == [
        (BACKGROUND_SOURCE, "normal", False, "The test run finished: all green.")
    ]


async def _requests_after_a_busy_turn(fakes, utterances, submitted) -> list[str]:
    """Queue `utterances` while a first turn runs, then return every request the brain got."""
    release = asyncio.Event()

    async def script(request, brain):
        if request == "first":
            await release.wait()
        yield fakes.DONE

    brain = fakes.Brain(script)
    status = StatusLine(io.StringIO())
    turns = BrainTurns(brain, submitted.append, ConversationState(WakeSettings()), status)
    worker = asyncio.create_task(turns.run())
    turns.add("first")
    await fakes.wait_until(lambda: brain.requests == ["first"])
    for utterance in utterances:
        turns.add(utterance)
    release.set()
    await fakes.wait_until(lambda: len(brain.requests) == 2)
    worker.cancel()
    return brain.requests


@pytest.mark.asyncio
async def test_utterances_during_a_turn_are_all_merged_into_one_request(fakes):
    submitted = []
    requests = await _requests_after_a_busy_turn(fakes, ["one", "two", "three", "four"], submitted)
    assert requests[1] == "one two three four"
    assert submitted == []


@pytest.mark.asyncio
async def test_speech_dropped_to_fit_the_cap_is_announced_not_silent(fakes):
    # Regression: the oldest queued utterance used to vanish with only a log line.
    long_utterance = "x" * (MAX_QUEUED_CHARS // 2)
    submitted = []
    utterances = [f"{name} {long_utterance}" for name in ("oldest", "middle", "newer")]
    requests = await _requests_after_a_busy_turn(fakes, [*utterances, "newest"], submitted)
    assert requests[1] == f"newer {long_utterance} newest"
    # Two utterances were dropped, but the user is told once per merged request.
    assert [(m.source, m.text) for m in submitted] == [(HUB_SOURCE, DROPPED_SPEECH_TEXT)]


@pytest.mark.asyncio
async def test_after_a_stop_dropped_speech_is_announced_again(fakes):
    release = asyncio.Event()

    async def script(request, brain):
        await release.wait()
        yield fakes.DONE

    submitted = []
    turns = BrainTurns(
        fakes.Brain(script),
        submitted.append,
        ConversationState(WakeSettings()),
        StatusLine(io.StringIO()),
    )
    worker = asyncio.create_task(turns.run())
    long_utterance = "x" * MAX_QUEUED_CHARS
    try:
        turns.add("first")
        await asyncio.sleep(0.01)
        turns.add(long_utterance)
        turns.add(long_utterance)  # drops the one before: announced
        await turns.cancel()  # "stop" discards the queue, notice and all
        turns.add(long_utterance)
        turns.add(long_utterance)  # a new drop is announced again
    finally:
        worker.cancel()
    assert [m.text for m in submitted] == [DROPPED_SPEECH_TEXT, DROPPED_SPEECH_TEXT]
