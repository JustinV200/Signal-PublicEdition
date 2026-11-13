"""Tests for TurnRouter: which events reach ask() and which go to the background handler."""

import asyncio

import pytest

from audiohub.brain import InjectedTurnDone, ReplyText, TurnActivity, TurnDone
from audiohub.brain.turn_router import TurnRouter

DONE = TurnDone(duration_s=1.0, cost_usd=0.01, is_error=False)
STALL_TIMEOUT_S = 1.0


class BackgroundRecorder:
    """An async on_background_text that records what it was given."""

    def __init__(self) -> None:
        self.texts: list[str] = []

    async def __call__(self, text: str) -> None:
        self.texts.append(text)


def drain(queue) -> list[object]:
    items = []
    while not queue.empty():
        items.append(queue.get_nowait())
    return items


@pytest.mark.asyncio
async def test_text_during_a_turn_goes_to_that_turn() -> None:
    background = BackgroundRecorder()
    router = TurnRouter(background)
    queue = router.begin_turn()
    await router.route(ReplyText("Paris."))
    await router.route(DONE)
    assert drain(queue) == [ReplyText("Paris."), DONE]
    assert background.texts == []
    assert not router.is_turn_open


@pytest.mark.asyncio
async def test_text_with_no_turn_open_goes_to_the_background_handler() -> None:
    background = BackgroundRecorder()
    router = TurnRouter(background)
    await router.route(ReplyText("Your agent finished."))
    await router.route(InjectedTurnDone())
    assert background.texts == ["Your agent finished."]


@pytest.mark.asyncio
async def test_an_injected_result_also_ends_the_users_turn() -> None:
    # Regression: the CLI folded a request into a turn it was already running,
    # so that turn's InjectedTurnDone was the only result, and the loop wedged.
    router = TurnRouter(BackgroundRecorder())
    queue = router.begin_turn()
    await router.route(ReplyText("Board's updated."))
    await router.route(InjectedTurnDone())
    events = drain(queue)
    assert events[0] == ReplyText("Board's updated.")
    assert isinstance(events[1], TurnDone) and not events[1].is_error
    assert not router.is_busy


@pytest.mark.asyncio
async def test_activity_keeps_an_injected_turn_waited_for_past_the_stall_timeout() -> None:
    router = TurnRouter(None)
    await router.route(TurnActivity())  # an injected turn starts
    waiting = asyncio.create_task(router.wait_until_idle(stall_timeout_s=0.2))
    for _ in range(8):  # 0.4 s of a foreground subagent at work in it
        await asyncio.sleep(0.05)
        await router.route(TurnActivity(is_subagent=True))
    assert not waiting.done()
    await router.route(InjectedTurnDone())
    await asyncio.wait_for(waiting, 1)


@pytest.mark.asyncio
async def test_a_stalled_injected_turn_is_given_up_on() -> None:
    router = TurnRouter(None)
    await router.route(TurnActivity())  # injected, and its result never comes
    await asyncio.wait_for(router.wait_until_idle(stall_timeout_s=0.02), 1)
    assert not router.is_busy


@pytest.mark.asyncio
async def test_a_mislabelled_result_cannot_trap_later_text_in_the_background() -> None:
    background = BackgroundRecorder()
    router = TurnRouter(background)
    await router.route(ReplyText("injected"))
    await router.route(DONE)  # The CLI didn't label the injected turn's result.
    queue = router.begin_turn()
    await router.route(ReplyText("answer"))
    assert drain(queue) == [ReplyText("answer")]


@pytest.mark.asyncio
async def test_sync_background_handler_is_supported() -> None:
    texts: list[str] = []
    router = TurnRouter(texts.append)
    await router.route(ReplyText("hello"))
    assert texts == ["hello"]


@pytest.mark.asyncio
async def test_failing_background_handler_is_logged_not_raised(
    caplog: pytest.LogCaptureFixture,
) -> None:
    def broken(text: str) -> None:
        raise ValueError("kernel down")

    router = TurnRouter(broken)
    await router.route(ReplyText("hello"))
    assert "on_background_text failed" in caplog.text


@pytest.mark.asyncio
async def test_end_turn_with_error_closes_the_turn() -> None:
    router = TurnRouter(None)
    queue = router.begin_turn()
    router.end_turn_with_error()
    [done] = drain(queue)
    assert isinstance(done, TurnDone) and done.is_error and done.cost_usd is None
    await router.wait_until_idle(STALL_TIMEOUT_S)


@pytest.mark.asyncio
async def test_only_one_turn_can_be_open() -> None:
    router = TurnRouter(None)
    router.begin_turn()
    with pytest.raises(RuntimeError, match="already open"):
        router.begin_turn()


@pytest.mark.asyncio
async def test_busy_covers_ask_turns_and_injected_turns() -> None:
    router = TurnRouter(None)
    assert not router.is_busy
    router.begin_turn()
    assert router.is_busy
    await router.route(DONE)
    assert not router.is_busy
    await router.route(TurnActivity())  # an injected turn's tool call, before any text
    assert router.is_busy
    await router.route(InjectedTurnDone())
    assert not router.is_busy
    await router.route(TurnActivity(is_subagent=True))  # a background agent at work
    assert not router.is_busy
