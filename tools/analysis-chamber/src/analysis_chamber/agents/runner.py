"""AgentRunner: runs one agent turn and returns its session id, final text and error flag.

SdkRunner is the real one, over claude_agent_sdk.ClaudeSDKClient (streaming mode,
which in-process MCP servers and hooks need). Phases depend only on the Protocol,
so tests swap in a fake.
"""

import dataclasses
from dataclasses import dataclass
from typing import Any, Protocol

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ClaudeSDKClient,
    ResultMessage,
    SystemMessage,
    TextBlock,
)

SUCCESS_SUBTYPE = "success"


@dataclass(frozen=True)
class TurnResult:
    """What one agent turn produced.

    Attributes:
        session_id: The SDK session id ("" if the CLI never reported one).
        text: The final answer text.
        is_error: False only for a ResultMessage with subtype "success" and
            is_error False; error_max_turns, other error subtypes and a turn
            with no ResultMessage at all are errors.
        structured: The validated-by-the-CLI JSON when the options set
            `output_format` (a json_schema), else None. Callers still validate it.
        permission_denied: True if the CLI denied any tool call in the turn
            (ResultMessage.permission_denials), e.g. a tool the mode didn't allow.
    """

    session_id: str
    text: str
    is_error: bool
    structured: Any = None
    permission_denied: bool = False


class AgentRunner(Protocol):
    """Runs one prompt to completion as an agent session."""

    async def run(
        self, options: ClaudeAgentOptions, prompt: str, resume: str | None = None
    ) -> TurnResult:
        """Run `prompt` with `options`, resuming session `resume` if given."""
        ...


class SdkRunner:
    """AgentRunner over the real Agent SDK. Stateless, so one instance serves every run."""

    async def run(
        self, options: ClaudeAgentOptions, prompt: str, resume: str | None = None
    ) -> TurnResult:
        """Run one turn in a fresh CLI process.

        Cancelling the awaiting task propagates into the message loop, and the
        client's context manager then disconnects, which stops the CLI.

        Args:
            options: The agent's options (from the option builders).
            prompt: The user message.
            resume: An SDK session id to resume, or None for a new session.

        Returns:
            The turn's result. Errors reported by the CLI come back as is_error.

        Raises:
            claude_agent_sdk.ClaudeSDKError: The CLI couldn't start or crashed.
        """
        if resume is not None:
            options = dataclasses.replace(options, resume=resume)
        session_id, texts = "", []
        async with ClaudeSDKClient(options) as client:
            await client.query(prompt)
            async for message in client.receive_response():
                if isinstance(message, SystemMessage) and message.subtype == "init":
                    session_id = message.data.get("session_id", session_id)
                elif isinstance(message, AssistantMessage):
                    texts.extend(b.text for b in message.content if isinstance(b, TextBlock))
                elif isinstance(message, ResultMessage):
                    # The result's text is the final answer; the assistant text is a fallback.
                    text = message.result if message.result is not None else "\n".join(texts)
                    return TurnResult(
                        message.session_id or session_id,
                        text,
                        message.subtype != SUCCESS_SUBTYPE or message.is_error,
                        message.structured_output,
                        bool(message.permission_denials),
                    )
        return TurnResult(session_id, "\n".join(texts), True)
