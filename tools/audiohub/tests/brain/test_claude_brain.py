"""Tests for ClaudeBrain with a scripted fake session (no SDK, no network).

Injected turns, merged turns and the stall watchdog are in test_claude_brain_turns.py.
"""

import asyncio

import pytest

from audiohub.brain import ReplyText, TurnDone
from audiohub.brain.permissions import PermissionRequest

DONE = TurnDone(duration_s=1.0, cost_usd=0.01, is_error=False)


@pytest.mark.asyncio
async def test_ask_yields_replies_then_turn_done(brain_kit) -> None:
    harness = brain_kit.Harness([[ReplyText("Paris."), ReplyText("Lovely city."), DONE]])
    async with harness.brain as brain:
        events = await brain_kit.collect(brain.ask("Capital of France?"))
    assert events == [ReplyText("Paris."), ReplyText("Lovely city."), DONE]
    assert harness.session.sent == ["Capital of France?"]


@pytest.mark.asyncio
async def test_turns_share_one_session(brain_kit) -> None:
    harness = brain_kit.Harness(
        [[ReplyText("Paris."), DONE], [ReplyText("About two million."), DONE]]
    )
    async with harness.brain as brain:
        await brain_kit.collect(brain.ask("Capital of France?"))
        second = await brain_kit.collect(brain.ask("Population?"))
    assert second == [ReplyText("About two million."), DONE]
    assert len(harness.sessions) == 1


@pytest.mark.asyncio
async def test_abandoned_ask_is_waited_out_before_the_next_one(brain_kit) -> None:
    harness = brain_kit.Harness([[ReplyText("a"), ReplyText("b"), DONE], [ReplyText("c"), DONE]])
    async with harness.brain as brain:
        async for _ in brain.ask("first"):
            break  # The loop stopped listening after the first reply.
        events = await brain_kit.collect(brain.ask("second"))
    assert events == [ReplyText("c"), DONE]


@pytest.mark.asyncio
async def test_concurrent_asks_are_serialised(brain_kit) -> None:
    harness = brain_kit.Harness([[ReplyText("one"), DONE], [ReplyText("two"), DONE]])
    async with harness.brain as brain:
        first, second = await asyncio.gather(
            brain_kit.collect(brain.ask("1")), brain_kit.collect(brain.ask("2"))
        )
    assert first == [ReplyText("one"), DONE]
    assert second == [ReplyText("two"), DONE]


@pytest.mark.asyncio
async def test_session_failure_ends_the_open_turn_and_later_asks_raise(brain_kit) -> None:
    harness = brain_kit.Harness([[ReplyText("partial")]])
    async with harness.brain as brain:
        turn = brain.ask("go")
        assert await anext(turn) == ReplyText("partial")
        harness.session.inject(ConnectionError("CLI crashed"))
        done = await anext(turn)
        assert isinstance(done, TurnDone) and done.is_error
        with pytest.raises(RuntimeError, match="ended") as raised:
            await brain_kit.collect(brain.ask("again"))
    assert isinstance(raised.value.__cause__, ConnectionError)


@pytest.mark.asyncio
async def test_interrupt_during_a_turn_reaches_the_session(brain_kit) -> None:
    harness = brain_kit.Harness([[ReplyText("counting")]])  # The turn is still running.
    async with harness.brain as brain:
        turn = brain.ask("count to 200")
        assert await anext(turn) == ReplyText("counting")
        await brain.interrupt()
        harness.session.inject(TurnDone(duration_s=0.1, cost_usd=0.0, is_error=True))
        done = await anext(turn)
        assert isinstance(done, TurnDone) and done.is_error
    assert harness.session.interrupt_count == 1


@pytest.mark.asyncio
async def test_interrupt_when_idle_does_nothing(brain_kit) -> None:
    harness = brain_kit.Harness([[DONE]])
    await harness.brain.interrupt()  # Not even started.
    async with harness.brain as brain:
        await brain_kit.collect(brain.ask("hi"))
        await brain.interrupt()
    assert harness.session.interrupt_count == 0


@pytest.mark.asyncio
async def test_start_and_close_are_idempotent(brain_kit) -> None:
    harness = brain_kit.Harness([])
    await harness.brain.start()
    await harness.brain.start()
    await harness.brain.close()
    await harness.brain.close()
    assert len(harness.sessions) == 1
    assert harness.session.disconnect_count == 1


@pytest.mark.asyncio
async def test_permission_requests_go_through_the_gate(brain_kit) -> None:
    harness = brain_kit.Harness([])
    async with harness.brain:
        decide = harness.session.decide_permission
        shell = await decide(PermissionRequest("Bash", {"command": "git status"}))
        read = await decide(PermissionRequest("Read", {"file_path": "a/b.py"}))
        assert (shell.is_allowed, read.is_allowed) == (False, True)
    assert harness.tool_calls == ["Read"]  # only allowed calls reach on_tool_call
