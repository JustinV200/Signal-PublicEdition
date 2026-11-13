"""The voice brain's own in-process tools, as an SDK MCP server.

Part of the thin SDK adapter (with sdk_options.py and sdk_session.py): the
tool logic lives SDK-free in handoff_tool/, and this module only registers it.
Every call still goes through the permission gate first, which always
allows the hand-off, without a spoken question.
"""

from typing import Any

from claude_agent_sdk import McpSdkServerConfig, create_sdk_mcp_server, tool

from audiohub.brain.handoff_tool import (
    HAND_OFF_DESCRIPTION,
    HAND_OFF_SERVER,
    HAND_OFF_TOOL,
    JOB_FIELD,
    HandOff,
)


def build_voice_server(hand_off: HandOff) -> McpSdkServerConfig:
    """The "voice" MCP server, with the hand-off tool calling `hand_off`.

    Args:
        hand_off: Sends the job; returns the text Claude gets back. Must not raise.

    Returns:
        A server config for ClaudeAgentOptions.mcp_servers, keyed by HAND_OFF_SERVER.
    """

    @tool(HAND_OFF_TOOL, HAND_OFF_DESCRIPTION, {JOB_FIELD: str})
    async def hand_off_to_main_session(args: dict[str, Any]) -> dict[str, Any]:
        job = args.get(JOB_FIELD)
        result = await hand_off(job if isinstance(job, str) else "")
        return {"content": [{"type": "text", "text": result}]}

    return create_sdk_mcp_server(HAND_OFF_SERVER, tools=[hand_off_to_main_session])
