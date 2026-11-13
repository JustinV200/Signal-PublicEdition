"""Tests for MessageTranslator against real claude-agent-sdk message dataclasses."""

import pytest
from claude_agent_sdk import (
    AssistantMessage,
    ConversationResetMessage,
    RateLimitEvent,
    RateLimitInfo,
    ResultMessage,
    StreamEvent,
    SystemMessage,
    TextBlock,
    ThinkingBlock,
    ToolResultBlock,
    ToolUseBlock,
    UserMessage,
)

from audiohub.brain import InjectedTurnDone, ReplyText, TurnActivity, TurnDone
from audiohub.brain.sdk_messages import MessageTranslator


def assistant(*blocks: object, parent_tool_use_id: str | None = None) -> AssistantMessage:
    return AssistantMessage(
        content=list(blocks), model="sonnet", parent_tool_use_id=parent_tool_use_id
    )


def result(
    total_cost_usd: float | None = 0.01,
    duration_ms: int = 1500,
    is_error: bool = False,
    terminal_reason: str | None = None,
    origin: dict[str, str] | None = None,
) -> ResultMessage:
    return ResultMessage(
        subtype="success",
        duration_ms=duration_ms,
        duration_api_ms=duration_ms,
        is_error=is_error,
        num_turns=1,
        session_id="session",
        total_cost_usd=total_cost_usd,
        terminal_reason=terminal_reason,
        origin=origin,  # type: ignore[arg-type]
    )


@pytest.mark.parametrize(
    ("is_error", "terminal_reason"), [(True, None), (False, "aborted_streaming")]
)
def test_error_or_interrupted_turn_is_flagged(is_error: bool, terminal_reason: str | None) -> None:
    [done] = MessageTranslator().translate(
        result(is_error=is_error, terminal_reason=terminal_reason)
    )
    assert isinstance(done, TurnDone) and done.is_error is True


@pytest.mark.parametrize("origin", [None, {"kind": "human"}, {"server": "no kind given"}])
def test_results_of_our_own_prompts_end_the_turn(origin: dict[str, str] | None) -> None:
    [done] = MessageTranslator().translate(result(origin=origin))
    assert isinstance(done, TurnDone)


@pytest.mark.parametrize("kind", ["task-notification", "peer"])
def test_results_of_injected_turns_are_marked_injected(kind: str) -> None:
    assert MessageTranslator().translate(result(origin={"kind": kind})) == [InjectedTurnDone()]


def test_injected_turn_cost_is_not_charged_to_the_next_turn() -> None:
    translator = MessageTranslator()
    translator.translate(result(total_cost_usd=0.02))
    translator.translate(result(total_cost_usd=0.05, origin={"kind": "task-notification"}))
    [done] = translator.translate(result(total_cost_usd=0.06))
    assert isinstance(done, TurnDone) and done.cost_usd == pytest.approx(0.01)


def test_each_text_block_becomes_one_reply_in_order() -> None:
    message = assistant(TextBlock("First."), TextBlock("Second."))
    assert MessageTranslator().translate(message) == [ReplyText("First."), ReplyText("Second.")]


def test_tool_use_and_thinking_blocks_are_skipped() -> None:
    message = assistant(
        ThinkingBlock(thinking="hmm", signature="sig"),
        TextBlock("Checking."),
        ToolUseBlock(id="t1", name="Bash", input={"command": "git status"}),
    )
    assert MessageTranslator().translate(message) == [ReplyText("Checking.")]


def test_blank_text_blocks_are_skipped() -> None:
    assert MessageTranslator().translate(assistant(TextBlock("  \n"))) == [TurnActivity()]


def test_subagent_text_is_not_spoken() -> None:
    message = assistant(TextBlock("internal notes"), parent_tool_use_id="agent-1")
    assert MessageTranslator().translate(message) == [TurnActivity(is_subagent=True)]


@pytest.mark.parametrize(
    "message",
    [
        assistant(ToolUseBlock(id="t1", name="Bash", input={"command": "git status"})),
        UserMessage(content=[ToolResultBlock(tool_use_id="t1", content="ok")]),
        UserMessage(content="a message from another session", origin={"kind": "peer"}),
    ],
)
def test_work_without_speakable_text_shows_a_turn_is_running(message: object) -> None:
    # Regression: an injected turn's tool calls used to produce nothing, so the
    # brain thought Claude was idle and sent the user's request into that turn.
    assert MessageTranslator().translate(message) == [TurnActivity()]  # type: ignore[arg-type]


def test_result_becomes_turn_done() -> None:
    done = MessageTranslator().translate(result(total_cost_usd=0.02, duration_ms=2500))
    assert done == [TurnDone(duration_s=2.5, cost_usd=0.02, is_error=False)]


def test_turn_cost_is_the_increase_in_the_running_session_total() -> None:
    translator = MessageTranslator()
    [first] = translator.translate(result(total_cost_usd=0.0337))
    [second] = translator.translate(result(total_cost_usd=0.0594))
    [third] = translator.translate(result(total_cost_usd=0.0594))
    assert isinstance(first, TurnDone) and first.cost_usd == pytest.approx(0.0337)
    assert isinstance(second, TurnDone) and second.cost_usd == pytest.approx(0.0257)
    assert isinstance(third, TurnDone) and third.cost_usd == pytest.approx(0.0)


def test_missing_cost_is_none_and_keeps_the_running_total() -> None:
    translator = MessageTranslator()
    translator.translate(result(total_cost_usd=0.03))
    [unknown] = translator.translate(result(total_cost_usd=None))
    [after] = translator.translate(result(total_cost_usd=0.05))
    assert isinstance(unknown, TurnDone) and unknown.cost_usd is None
    assert isinstance(after, TurnDone) and after.cost_usd == pytest.approx(0.02)


def test_conversation_reset_zeroes_the_running_total() -> None:
    translator = MessageTranslator()
    translator.translate(result(total_cost_usd=0.05))
    reset = ConversationResetMessage(new_conversation_id="c2", uuid="u", session_id="s")
    assert translator.translate(reset) == []
    [done] = translator.translate(result(total_cost_usd=0.01))
    assert isinstance(done, TurnDone) and done.cost_usd == pytest.approx(0.01)


def test_a_falling_total_without_a_reset_counts_as_a_fresh_total() -> None:
    translator = MessageTranslator()
    translator.translate(result(total_cost_usd=0.05))
    [done] = translator.translate(result(total_cost_usd=0.01))
    assert isinstance(done, TurnDone) and done.cost_usd == pytest.approx(0.01)


@pytest.mark.parametrize(
    "message",
    [
        SystemMessage(subtype="init", data={}),
        StreamEvent(uuid="u", session_id="s", event={}),
        RateLimitEvent(rate_limit_info=RateLimitInfo(status="allowed"), uuid="u", session_id="s"),
    ],
)
def test_other_messages_produce_no_events(message: object) -> None:
    assert MessageTranslator().translate(message) == []  # type: ignore[arg-type]
