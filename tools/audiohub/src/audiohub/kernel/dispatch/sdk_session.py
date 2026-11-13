"""Low-level helpers for one Claude Agent SDK session used by the dispatcher backend.

The helpers build the session options, run one turn and collect its text, and
disconnect with a time limit. Session lifecycle (when to connect, reuse or
replace) lives in backend.py.
"""

import asyncio
import logging
import tempfile

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ClaudeSDKClient,
    ResultMessage,
    TextBlock,
)

logger = logging.getLogger(__name__)

# TODO: move to KernelSettings once audiohub.config is free to edit.
DISCONNECT_TIMEOUT_S = 5.0


class BackendError(RuntimeError):
    """The SDK session reported an error instead of a reply."""


def session_options(model: str, system_prompt: str) -> ClaudeAgentOptions:
    """SDK options for a fast, isolated, tool-less single-turn dispatcher.

    Args:
        model: Model alias or id, e.g. "sonnet".
        system_prompt: The dispatcher's system prompt.

    Returns:
        Options for `ClaudeSDKClient`.
    """
    return ClaudeAgentOptions(
        model=model,
        system_prompt=system_prompt,
        tools=[],  # no built-in tools at all
        # No user/project settings or CLAUDE.md: irrelevant to ordering, and slow.
        setting_sources=[],
        strict_mcp_config=True,  # ignore .mcp.json and user MCP servers
        max_turns=1,
        thinking={"type": "disabled"},  # roughly halved latency in measurements
        # Message text comes from other agents: never expand @file mentions in it.
        verbatim_prompts=True,
        # A neutral cwd so nothing project-specific is discovered.
        cwd=tempfile.gettempdir(),
        # Decisions are throwaway; don't litter ~/.claude/projects with transcripts.
        extra_args={"no-session-persistence": None},
        stderr=lambda line: logger.debug("dispatcher CLI: %s", line),
    )


async def ask_turn(client: ClaudeSDKClient, prompt: str) -> str:
    """Send one turn and collect the assistant's text until the result arrives.

    Raises:
        BackendError: If the assistant message or the result reports an error.
    """
    await client.query(prompt)
    parts: list[str] = []
    async for message in client.receive_response():
        if isinstance(message, AssistantMessage):
            if message.error:
                raise BackendError(f"assistant error from the dispatcher model: {message.error}")
            parts.extend(block.text for block in message.content if isinstance(block, TextBlock))
        elif isinstance(message, ResultMessage) and message.is_error:
            raise BackendError(f"dispatcher turn failed: {message.subtype} {message.errors}")
    return "".join(parts)


async def disconnect_quietly(client: ClaudeSDKClient) -> None:
    """Disconnect within `DISCONNECT_TIMEOUT_S`, logging (not raising) any failure.

    Used on sessions being thrown away, where a failed disconnect must not
    mask the error that caused it or block the next session.
    """
    try:
        async with asyncio.timeout(DISCONNECT_TIMEOUT_S):
            await client.disconnect()
    except TimeoutError:
        logger.warning("dispatcher session took over %.0f s to disconnect", DISCONNECT_TIMEOUT_S)
    except Exception:
        logger.exception("error while disconnecting a dispatcher session")
