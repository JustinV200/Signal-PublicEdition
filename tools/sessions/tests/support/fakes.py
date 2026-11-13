"""Shared fakes for the sessions tests: a scripted SDK client, a gated approver, a recording hub.

Nothing here starts a CLI or reaches the network. FakeClient implements the
sdk.SessionClient protocol and emits real claude_agent_sdk message objects,
so the real translator and can_use_tool wrapper run in the tests.
"""

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ResultMessage,
    SystemMessage,
    TextBlock,
    ToolPermissionContext,
)
from signal_hub_notify import HubNote

from claude_sessions.approvals import ApprovalRequest

_END = object()

# What a FakeClient does with each prompt: script(client, prompt).
Script = Callable[["FakeClient", str], Awaitable[None]]


def assistant_text(text: str, parent_tool_use_id: str | None = None) -> AssistantMessage:
    """An assistant message with one text block."""
    return AssistantMessage(
        content=[TextBlock(text=text)], model="sonnet", parent_tool_use_id=parent_tool_use_id
    )


def result(session_id: str, text: str = "", cost: float = 0.01, subtype: str = "success"):
    """A ResultMessage ending a turn."""
    return ResultMessage(
        subtype=subtype,
        duration_ms=5,
        duration_api_ms=4,
        is_error=subtype != "success",
        num_turns=1,
        session_id=session_id,
        total_cost_usd=cost,
        result=text,
    )


async def reply_with_echo(client: "FakeClient", prompt: str) -> None:
    """Default script: init message, then "echo: <prompt>" and a result."""
    session_id = client.options.session_id or client.options.resume
    client.emit(SystemMessage(subtype="init", data={"session_id": session_id}))
    reply = "pong" if "pong" in prompt else f"echo: {prompt}"
    client.emit(assistant_text(reply))
    client.emit(result(session_id, reply, cost=0.01 * len(client.queries)))


class FakeClient:
    """A scripted stand-in for ClaudeSDKClient."""

    def __init__(self, options: ClaudeAgentOptions, script: Script) -> None:
        self.options = options
        self.queries: list[str] = []
        self.is_connected = False
        self.is_disconnected = False
        self._script = script
        self._messages: asyncio.Queue[Any] = asyncio.Queue()
        self._tasks: set[asyncio.Task[None]] = set()

    async def connect(self) -> None:
        self.is_connected = True

    async def query(self, prompt: str) -> None:
        self.queries.append(prompt)
        task = asyncio.create_task(self._script(self, prompt))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def receive_messages(self):
        while (message := await self._messages.get()) is not _END:
            yield message

    async def interrupt(self) -> None:
        """Not used by the daemon; present to satisfy the protocol."""

    async def disconnect(self) -> None:
        self.is_disconnected = True
        self.end_stream()

    def emit(self, message: Any) -> None:
        """Queue one message for the session's reader."""
        self._messages.put_nowait(message)

    def end_stream(self) -> None:
        """End receive_messages, as when the CLI process exits."""
        self._messages.put_nowait(_END)

    async def ask_permission(self, tool_name: str, tool_input: dict[str, Any], title: str):
        """Call the session's can_use_tool the way the SDK does for a prompted tool call."""
        context = ToolPermissionContext(tool_use_id="tu1", title=title)
        return await self.options.can_use_tool(tool_name, tool_input, context)


class FakeClientFactory:
    """Builds FakeClients with one script and remembers them."""

    def __init__(self, script: Script = reply_with_echo) -> None:
        self.script = script
        self.clients: list[FakeClient] = []

    def __call__(self, options: ClaudeAgentOptions) -> FakeClient:
        client = FakeClient(options, self.script)
        self.clients.append(client)
        return client


class FakeApprover:
    """Records requests; answers `answer` once `release` is set (set by default)."""

    def __init__(self, answer: bool = True) -> None:
        self.answer = answer
        self.requests: list[ApprovalRequest] = []
        self.release = asyncio.Event()
        self.release.set()

    async def approve(self, request: ApprovalRequest) -> bool:
        self.requests.append(request)
        request.on_shown()  # As DialogApprover does when its dialog appears.
        await self.release.wait()
        return self.answer


class RecordingHub:
    """A fake send_to_hub that records notes, or raises `error` when set."""

    def __init__(self) -> None:
        self.notes: list[HubNote] = []
        self.error: Exception | None = None

    async def __call__(self, host: str, port: int, note: HubNote, token: str) -> str:
        assert token, "notes must carry the hub's token"
        if self.error is not None:
            raise self.error
        self.notes.append(note)
        return f"m{len(self.notes)}"
