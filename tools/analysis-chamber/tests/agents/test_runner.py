"""SdkRunner: only a clean "success" result is not an error."""

import pytest
from claude_agent_sdk import ClaudeAgentOptions, ResultMessage, SystemMessage

from analysis_chamber.agents import SdkRunner
from analysis_chamber.agents import runner as runner_module


def _result(subtype: str, is_error: bool, denials: list | None = None) -> ResultMessage:
    return ResultMessage(
        subtype=subtype,
        duration_ms=1,
        duration_api_ms=1,
        is_error=is_error,
        num_turns=1,
        session_id="s-1",
        result="done",
        permission_denials=denials,
    )


class FakeClient:
    """Stands in for ClaudeSDKClient, replaying `messages`."""

    messages: list = []

    def __init__(self, options):
        self.options = options

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def query(self, prompt):
        pass

    async def receive_response(self):
        for message in self.messages:
            yield message


INIT = SystemMessage("init", {"session_id": "s-1"})


@pytest.mark.parametrize(
    ("messages", "is_error", "denied"),
    [
        ([INIT, _result("success", False)], False, False),
        ([INIT, _result("error_max_turns", False)], True, False),
        ([INIT, _result("success", True)], True, False),
        ([INIT], True, False),  # no ResultMessage at all
        ([INIT, _result("success", False, [{"tool_name": "WebSearch"}])], False, True),
    ],
)
@pytest.mark.asyncio
async def test_is_error_unless_clean_success(monkeypatch, messages, is_error, denied):
    monkeypatch.setattr(FakeClient, "messages", messages)
    monkeypatch.setattr(runner_module, "ClaudeSDKClient", FakeClient)
    turn = await SdkRunner().run(ClaudeAgentOptions(), "hi")
    assert turn.is_error is is_error and turn.session_id == "s-1"
    assert turn.permission_denied is denied
