"""Tests for the MCP `notify` tool, with the kernel client replaced by a recording fake."""

import pytest

from audiohub.kernel import HubNotRunningError, NotificationDroppedError, ProtocolError

pytestmark = pytest.mark.asyncio


async def test_forwards_text_priority_and_source_to_the_hub(notify_tool, kernel_client) -> None:
    result = await notify_tool.notify("Build finished.", priority="high", source="build-agent")
    assert kernel_client.calls == [("127.0.0.1", 8765, "build-agent", "Build finished.", "high")]
    assert "m1" in result


async def test_hub_not_running_says_message_was_not_delivered(notify_tool, kernel_client) -> None:
    kernel_client.error = HubNotRunningError(
        "audiohub isn't running on 127.0.0.1:8765; start it with `uv run audiohub run`"
    )
    result = await notify_tool.notify("Hello.")
    assert result.startswith("The audiohub voice hub isn't running")
    assert "was not delivered and the user did not hear it" in result
    # The model should tell the user, not try to launch the hub from the error's start hint.
    assert "Tell the user the voice hub isn't running" in result
    assert "uv run" not in result


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (ProtocolError('"text" must be a non-blank string'), "The message was rejected"),
        # The request was already sent, so delivery is uncertain rather than failed.
        (TimeoutError(), "may not have been delivered"),
        (ConnectionResetError("reset by peer"), "connection to the voice hub failed"),
        (NotificationDroppedError("dropped: the owner is asleep"), "Not spoken"),
    ],
)
async def test_other_failures_become_explanations(
    notify_tool, kernel_client, error, expected
) -> None:
    kernel_client.error = error
    result = await notify_tool.notify("Hello.")
    assert expected in result
    assert (str(error) or type(error).__name__) in result
