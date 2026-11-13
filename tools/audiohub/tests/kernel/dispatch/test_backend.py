"""Tests for SonnetBackend's session handling, with the SDK client replaced by a fake.

No network: `FakeClient` stands in for `ClaudeSDKClient` and replays canned
SDK messages, so warm-up, reset-every-N and replace-on-failure can be checked.
"""

import asyncio

import pytest
from claude_agent_sdk import AssistantMessage, ResultMessage, TextBlock

from audiohub.kernel.dispatch import BackendClosedError, BackendError, SonnetBackend
from audiohub.kernel.dispatch import backend as backend_module

pytestmark = pytest.mark.asyncio


class FakeClient:
    """Mimics the parts of ClaudeSDKClient the backend uses."""

    instances: list["FakeClient"] = []
    connect_delay_s = 0.0  # set on the class to make the next connects hang

    def __init__(self, options) -> None:
        self.options = options
        self.prompts: list[str] = []
        self.connected = False
        self.disconnected = False
        self.fail_next = False
        self.delay_s = 0.0
        FakeClient.instances.append(self)

    async def connect(self) -> None:
        await asyncio.sleep(FakeClient.connect_delay_s)
        self.connected = True

    async def disconnect(self) -> None:
        self.disconnected = True

    async def query(self, prompt: str) -> None:
        self.prompts.append(prompt)

    async def receive_response(self):
        await asyncio.sleep(self.delay_s)
        text = f"reply to {self.prompts[-1]}"
        yield AssistantMessage(content=[TextBlock(text[:6]), TextBlock(text[6:])], model="fake")
        yield ResultMessage("success", 1, 1, self.fail_next, 1, "session")


@pytest.fixture(autouse=True)
def fake_sdk(monkeypatch):
    FakeClient.instances = []
    FakeClient.connect_delay_s = 0.0
    monkeypatch.setattr(backend_module, "ClaudeSDKClient", FakeClient)


async def settle() -> None:
    """Let background connect/disconnect tasks run."""
    for _ in range(5):
        await asyncio.sleep(0)


async def test_start_connects_and_warms_up_once() -> None:
    backend = SonnetBackend("sonnet", "system", reset_every=5)
    await backend.start()
    assert await backend.complete("a") == "reply to a"
    (client,) = FakeClient.instances
    assert client.prompts == [backend_module.WARM_UP_PROMPT, "a"]
    await backend.close()
    assert client.disconnected


async def test_session_options_are_isolated_and_tool_less() -> None:
    backend = SonnetBackend("sonnet", "system prompt")
    await backend.complete("a")
    options = FakeClient.instances[0].options
    assert (options.model, options.system_prompt, options.tools) == ("sonnet", "system prompt", [])
    assert options.setting_sources == [] and options.max_turns == 1
    await backend.close()


async def test_session_is_replaced_after_reset_every_decisions() -> None:
    backend = SonnetBackend("sonnet", "system", reset_every=2)
    for prompt in ("a", "b", "c"):
        await backend.complete(prompt)
    await settle()
    first, second = FakeClient.instances
    assert first.prompts[1:] == ["a", "b"] and first.disconnected
    assert second.prompts[1:] == ["c"] and not second.disconnected
    await backend.close()


async def test_error_result_raises_and_replaces_session() -> None:
    backend = SonnetBackend("sonnet", "system")
    await backend.start()
    FakeClient.instances[0].fail_next = True
    with pytest.raises(BackendError):
        await backend.complete("a")
    await settle()
    assert FakeClient.instances[0].disconnected
    assert await backend.complete("b") == "reply to b"
    assert FakeClient.instances[1].prompts[-1] == "b"
    await backend.close()


async def test_timeout_discards_session_so_late_replies_cannot_leak() -> None:
    backend = SonnetBackend("sonnet", "system")
    await backend.start()
    FakeClient.instances[0].delay_s = 1.0
    with pytest.raises(TimeoutError):
        await asyncio.wait_for(backend.complete("slow"), 0.05)
    await settle()
    assert FakeClient.instances[0].disconnected
    assert await backend.complete("next") == "reply to next"
    await backend.close()


async def test_hung_connect_times_out_and_the_next_call_retries(monkeypatch) -> None:
    monkeypatch.setattr(backend_module, "CONNECT_TIMEOUT_S", 0.05)
    FakeClient.connect_delay_s = 10.0
    backend = SonnetBackend("sonnet", "system")
    with pytest.raises(TimeoutError):
        await backend.start()
    assert FakeClient.instances[0].disconnected
    FakeClient.connect_delay_s = 0.0
    assert await backend.complete("a") == "reply to a"
    assert len(FakeClient.instances) == 2
    await backend.close()


async def test_caller_timeout_during_connect_keeps_the_shared_connect() -> None:
    FakeClient.connect_delay_s = 0.2
    backend = SonnetBackend("sonnet", "system")
    with pytest.raises(TimeoutError):
        await asyncio.wait_for(backend.complete("a"), 0.05)
    FakeClient.connect_delay_s = 0.0
    assert await backend.complete("b") == "reply to b"
    assert len(FakeClient.instances) == 1
    await backend.close()


async def test_calls_after_close_raise_instead_of_reconnecting() -> None:
    backend = SonnetBackend("sonnet", "system")
    await backend.complete("a")
    await backend.close()
    with pytest.raises(BackendClosedError):
        await backend.complete("b")
    with pytest.raises(BackendClosedError):
        await backend.start()
    assert len(FakeClient.instances) == 1
