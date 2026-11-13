"""Tests for SdkSession with a fake ClaudeSDKClient (no CLI, no network)."""

from collections import deque
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    Message,
    ResultMessage,
    SystemMessage,
    TextBlock,
)

from audiohub.brain import InjectedTurnDone, ReplyText, TurnDone
from audiohub.brain.permissions import PermissionDecision, PermissionRequest
from audiohub.brain.sdk_session import SdkSession
from audiohub.config import BrainSettings


class FakeClient:
    """Mimics the ClaudeSDKClient calls SdkSession makes."""

    def __init__(self, options: ClaudeAgentOptions) -> None:
        self.options = options
        self.is_connected = False
        self.queries: list[str] = []
        self.interrupt_count = 0
        self.messages: deque[Message] = deque()

    async def connect(self) -> None:
        self.is_connected = True

    async def disconnect(self) -> None:
        self.is_connected = False

    async def query(self, prompt: str) -> None:
        self.queries.append(prompt)

    async def receive_messages(self) -> AsyncIterator[Message]:
        # The real stream spans every turn; this one ends when the script runs out.
        while self.messages:
            yield self.messages.popleft()

    async def interrupt(self) -> None:
        self.interrupt_count += 1


async def allow_everything(request: PermissionRequest) -> PermissionDecision:
    return PermissionDecision(True)


async def hand_off_nowhere(job: str) -> str:
    return "not sent"


def make_session() -> tuple[SdkSession, list[FakeClient]]:
    clients: list[FakeClient] = []

    def factory(options: ClaudeAgentOptions) -> FakeClient:
        clients.append(FakeClient(options))
        return clients[-1]

    session = SdkSession(
        BrainSettings(model="sonnet"),
        Path(r"C:\src\Signal"),
        allow_everything,
        hand_off_nowhere,
        client_factory=factory,  # type: ignore[arg-type]
    )
    return session, clients


def result_message(total_cost_usd: float, origin: dict[str, str] | None = None) -> ResultMessage:
    return ResultMessage(
        subtype="success",
        duration_ms=1000,
        duration_api_ms=900,
        is_error=False,
        num_turns=1,
        session_id="s",
        total_cost_usd=total_cost_usd,
        origin=origin,  # type: ignore[arg-type]
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("resume", [None, "conv-1"])
async def test_connect_builds_one_client_from_the_options(resume: str | None) -> None:
    session, clients = make_session()
    await session.connect(resume)
    [client] = clients
    assert client.is_connected
    assert (client.options.model, client.options.effort) == ("sonnet", "low")
    assert client.options.resume == resume  # a reconnect carries the conversation on
    assert client.options.cwd == r"C:\src\Signal"


@pytest.mark.asyncio
async def test_send_forwards_the_prompt() -> None:
    session, clients = make_session()
    await session.connect()
    await session.send("Capital of France?")
    assert clients[0].queries == ["Capital of France?"]


@pytest.mark.asyncio
async def test_events_span_turns_including_injected_ones() -> None:
    session, clients = make_session()
    await session.connect()
    clients[0].messages.extend(
        [
            SystemMessage(subtype="init", data={}),
            AssistantMessage(content=[TextBlock("Paris.")], model="sonnet"),
            result_message(total_cost_usd=0.02),
            AssistantMessage(content=[TextBlock("Your agent finished.")], model="sonnet"),
            result_message(total_cost_usd=0.03, origin={"kind": "task-notification"}),
            AssistantMessage(content=[TextBlock("About two million.")], model="sonnet"),
            result_message(total_cost_usd=0.05),
        ]
    )
    events = [event async for event in session.events()]
    assert events == [
        ReplyText("Paris."),
        TurnDone(duration_s=1.0, cost_usd=0.02, is_error=False),
        ReplyText("Your agent finished."),
        InjectedTurnDone(),
        ReplyText("About two million."),
        TurnDone(duration_s=1.0, cost_usd=pytest.approx(0.02), is_error=False),
    ]
    assert session.session_id == "s"  # taken from the results, for a later resume


@pytest.mark.asyncio
async def test_interrupt_reaches_the_client() -> None:
    session, clients = make_session()
    await session.connect()
    await session.interrupt()
    assert clients[0].interrupt_count == 1


@pytest.mark.asyncio
async def test_disconnect_is_safe_twice() -> None:
    session, clients = make_session()
    await session.connect()
    await session.disconnect()
    await session.disconnect()
    assert not clients[0].is_connected


@pytest.mark.asyncio
async def test_calls_before_connect_raise_a_clear_error() -> None:
    session, _ = make_session()
    with pytest.raises(RuntimeError, match="connect"):
        await session.send("hello")
    with pytest.raises(RuntimeError, match="connect"):
        await session.interrupt()
