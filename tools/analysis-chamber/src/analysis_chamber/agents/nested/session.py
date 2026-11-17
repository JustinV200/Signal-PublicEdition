"""Options and the run calls shared by every nested sub-agent session.

Nested sessions run inside the lead's chamber tools (spike notes, not published:
a nested query works from an SDK MCP tool handler). Each one gets no settings,
strict MCP config and a JSON-schema output, and is bounded by a timeout so a
stuck session fails closed instead of hanging the lead.
"""

import asyncio
from pathlib import Path
from typing import Any

from claude_agent_sdk import ClaudeAgentOptions

from analysis_chamber.agents.nested.fields import NestedError, require_dict
from analysis_chamber.agents.runner import AgentRunner, TurnResult

# The env every chamber session gets, nested or not (options.base uses it too).
# ENABLE_CLAUDEAI_MCP_SERVERS keeps claude.ai connectors out even if strict_mcp_config
# were ever dropped; SIGNAL_BRIEF_SURFACE=managed stops brief tools marking anything seen.
# MAX_MCP_OUTPUT_TOKENS: past the CLI's default (25k tokens) an MCP result is swapped
# for a "too large, saved to <file>" notice before PostToolUse runs, so the free-text
# swap saved and extracted only the notice and the data was lost (live run 5).
MCP_OUTPUT_TOKEN_CAP = 150_000
SESSION_ENV = {
    "ENABLE_CLAUDEAI_MCP_SERVERS": "false",
    "SIGNAL_BRIEF_SURFACE": "managed",
    "MAX_MCP_OUTPUT_TOKENS": str(MCP_OUTPUT_TOKEN_CAP),
}


def nested_options(
    model: str, cwd: Path, system_prompt: str, schema: dict[str, Any], **overrides: Any
) -> ClaudeAgentOptions:
    """Options for a nested, settings-free, schema'd session.

    Args:
        model: The model (config.fetch_model).
        cwd: The run folder.
        system_prompt: The whole system prompt (no Claude Code preset).
        schema: The JSON schema the final output must match.
        **overrides: Other ClaudeAgentOptions fields (tools default to none).

    Returns:
        The options.
    """
    fields: dict[str, Any] = {
        "model": model,
        "cwd": str(cwd),
        "tools": [],
        "setting_sources": [],
        "strict_mcp_config": True,
        "mcp_servers": {},
        "system_prompt": system_prompt,
        "output_format": {"type": "json_schema", "schema": schema},
        "env": dict(SESSION_ENV),
    } | overrides
    return ClaudeAgentOptions(**fields)


async def run_turn(
    runner: AgentRunner, options: ClaudeAgentOptions, prompt: str, timeout_s: float
) -> TurnResult:
    """Run a nested session to a clean result.

    Raises:
        NestedError: The session errored or timed out.
    """
    try:
        result = await asyncio.wait_for(runner.run(options, prompt), timeout_s)
    except TimeoutError as error:
        raise NestedError(f"nested session timed out after {timeout_s:.0f}s") from error
    if result.is_error:
        raise NestedError("nested session reported an error")
    return result


async def run_structured(
    runner: AgentRunner, options: ClaudeAgentOptions, prompt: str, timeout_s: float
) -> dict:
    """Run a nested session and return its structured output (not yet field-checked).

    Raises:
        NestedError: The session errored, timed out or gave no structured output.
    """
    result = await run_turn(runner, options, prompt, timeout_s)
    return require_dict(result.structured)
