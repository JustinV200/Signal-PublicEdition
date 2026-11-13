"""ClaudeBrain tests for turns it didn't ask for: injected turns, merged turns, stalls.

A scripted fake session (`brain_kit`, tests/brain/conftest.py) plays the CLI.
"""

import asyncio

import pytest

from audiohub.brain import (
    InjectedTurnDone,
    ReplyText,
    TurnActivity,
    TurnDone,
    TurnStalledError,
    turn_watchdog,
)
from audiohub.config import BrainSettings

DONE = TurnDone(duration_s=1.0, cost_usd=0.01, is_error=False)


@pytest.mark.asyncio
async def test_injected_turn_between_asks_goes_to_the_background_not_the_next_reply(
    brain_kit,
) -> None:
    harness = brain_kit.Harness(
        [[ReplyText("Started an agent."), DONE], [ReplyText("Next answer."), DONE]]
    )
    async with harness.brain as brain:
        await brain_kit.collect(brain.ask("Start a background agent"))
        harness.session.inject(ReplyText("The agent finished."), InjectedTurnDone())
        await brain_kit.wait_until(lambda: harness.background == ["The agent finished."])
        events = await brain_kit.collect(brain.ask("Anything else?"))
    assert events == [ReplyText("Next answer."), DONE]


@pytest.mark.asyncio
async def test_ask_waits_for_a_turn_claude_started_on_its_own(brain_kit) -> None:
    # Regression: a request sent while an injected turn was busy but hadn't
    # written text yet was folded into it, never got a result, and wedged the loop.
    harness = brain_kit.Harness([[ReplyText("Your answer."), DONE]])
    async with harness.brain as brain:
        harness.session.inject(TurnActivity())  # e.g. another session's message, at work
        await brain_kit.wait_until(harness.session.stream.empty)
        asking = asyncio.create_task(brain_kit.collect(brain.ask("What can you do?")))
        for _ in range(10):
            await asyncio.sleep(0)
        assert harness.session.sent == []
        harness.session.inject(ReplyText("Board's updated."), InjectedTurnDone())
        events = await asyncio.wait_for(asking, 1)
    assert harness.background == ["Board's updated."]
    assert events == [ReplyText("Your answer."), DONE]


@pytest.mark.asyncio
async def test_stop_while_a_request_waits_for_an_injected_turn_means_it_is_never_sent(
    brain_kit,
) -> None:
    # Regression: the interrupt ended the injected turn, then the waiting
    # request was sent anyway, so its auto-allowed tools ran after "stop".
    harness = brain_kit.Harness([[ReplyText("Deleted it."), DONE]])
    async with harness.brain as brain:
        harness.session.inject(TurnActivity())
        await brain_kit.wait_until(harness.session.stream.empty)
        asking = asyncio.create_task(brain_kit.collect(brain.ask("delete the branch")))
        for _ in range(10):  # let ask() reach its wait for the injected turn
            await asyncio.sleep(0)
        await brain.interrupt()
        harness.session.inject(InjectedTurnDone())
        [done] = await asyncio.wait_for(asking, 1)
    assert harness.session.interrupt_count == 1
    assert harness.session.sent == []
    assert isinstance(done, TurnDone) and done.is_error


@pytest.mark.asyncio
async def test_a_merged_turn_ends_on_the_injected_result(brain_kit) -> None:
    harness = brain_kit.Harness([[ReplyText("Board's updated."), InjectedTurnDone()]])
    async with harness.brain as brain:
        events = await asyncio.wait_for(brain_kit.collect(brain.ask("question")), 1)
    assert events[0] == ReplyText("Board's updated.")
    assert isinstance(events[1], TurnDone)


@pytest.mark.asyncio
async def test_a_turn_with_no_activity_is_given_up_and_the_next_ask_works(brain_kit) -> None:
    settings = BrainSettings(turn_stall_timeout_s=0.05)
    harness = brain_kit.Harness(
        [[TurnActivity()], [ReplyText("Back again."), DONE]], settings=settings
    )
    async with harness.brain as brain:
        with pytest.raises(TurnStalledError):
            await brain_kit.collect(brain.ask("hello?"))
        events = await asyncio.wait_for(brain_kit.collect(brain.ask("hello again")), 1)
    assert events == [ReplyText("Back again."), DONE]


@pytest.mark.asyncio
async def test_a_stalled_turns_late_answer_goes_to_the_background_not_the_next_request(
    brain_kit,
) -> None:
    settings = BrainSettings(turn_stall_timeout_s=0.2)
    harness = brain_kit.Harness([[], [ReplyText("Answer to B."), DONE]], settings=settings)
    async with harness.brain as brain:
        with pytest.raises(TurnStalledError):
            await brain_kit.collect(brain.ask("A"))
        harness.session.inject(ReplyText("Answer to A."), DONE)  # A's result, too late
        events = await asyncio.wait_for(brain_kit.collect(brain.ask("B")), 1)
    assert harness.session.interrupt_count == 1  # the watchdog asked the CLI to stop A
    assert harness.background == ["Answer to A."]
    assert events == [ReplyText("Answer to B."), DONE]


@pytest.mark.asyncio
async def test_steady_activity_keeps_a_turn_alive_past_the_stall_timeout(brain_kit) -> None:
    settings = BrainSettings(turn_stall_timeout_s=0.2)
    harness = brain_kit.Harness([[]], settings=settings)
    async with harness.brain as brain:
        asking = asyncio.create_task(brain_kit.collect(brain.ask("run the long build")))
        for _ in range(8):  # 0.4 s of tool calls, twice the stall timeout
            await asyncio.sleep(0.05)
            harness.session.inject(TurnActivity())
        harness.session.inject(ReplyText("Build passed."), DONE)
        events = await asyncio.wait_for(asking, 1)
    assert events == [ReplyText("Build passed."), DONE]


@pytest.mark.asyncio
async def test_restart_after_dying_mid_injected_turn_routes_replies_to_ask(brain_kit) -> None:
    harness = brain_kit.Harness([[ReplyText("fresh answer"), DONE]])
    await harness.brain.start()
    harness.session.inject(ReplyText("agent result, part one"))  # injected turn starts
    harness.session.inject(ConnectionError("CLI crashed"))  # ...and never ends
    await brain_kit.wait_until(lambda: bool(harness.background))
    await harness.brain.close()
    async with harness.brain as brain:
        events = await brain_kit.collect(brain.ask("hello again"))
    assert events == [ReplyText("fresh answer"), DONE]


@pytest.mark.asyncio
async def test_interrupt_reaches_an_injected_turn(brain_kit) -> None:
    harness = brain_kit.Harness([])
    async with harness.brain as brain:
        harness.session.inject(ReplyText("Working on the agent result."))
        await brain_kit.wait_until(lambda: bool(harness.background))
        await brain.interrupt()
    assert harness.session.interrupt_count == 1


@pytest.mark.asyncio
async def test_a_cli_that_hangs_on_interrupt_doesnt_hold_up_the_stall_report(
    brain_kit, monkeypatch
) -> None:
    monkeypatch.setattr(turn_watchdog, "STALLED_INTERRUPT_TIMEOUT_S", 0.05)
    harness = brain_kit.Harness([[]], settings=BrainSettings(turn_stall_timeout_s=0.05))

    async def hang() -> None:
        await asyncio.Event().wait()

    async with harness.brain as brain:
        harness.session.interrupt = hang
        with pytest.raises(TurnStalledError):
            await asyncio.wait_for(brain_kit.collect(brain.ask("hello?")), 1)
