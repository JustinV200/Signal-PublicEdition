"""role_options: the fields every chamber session shares, whatever its role.

- bypassPermissions: runs never prompt (spec 13). The send block is security's
  disallowed list plus its PreToolUse hooks, which both hold under bypass
  (spike notes, not published). allowed_tools restricts nothing under
  bypass, so it isn't used for isolation.
- setting_sources=[]: no user or project settings, so no CLAUDE.md/AGENTS.md
  (the repo's orchestrator rules would have the lead delegate and commit), no
  user hooks (the brief prompt hook, notifications), no plugins and no
  permission rules. The playbook is pointed at in the system prompt instead,
  with its folder in add_dirs.
- strict_mcp_config=True with explicit servers: without it the claude.ai
  connectors (Gmail send, Calendar delete) load even with no settings (spike notes,
  not published). ENABLE_CLAUDEAI_MCP_SERVERS=false is a second layer.
- env: kit.run_env so python and uv pip target the run venv, plus
  SIGNAL_BRIEF_SURFACE=managed so brief tools never mark anything seen.
"""

from typing import Any

from claude_agent_sdk import ClaudeAgentOptions
from claude_agent_sdk.types import SystemPromptPreset

from analysis_chamber import kit, security
from analysis_chamber.agents.context import RunContext
from analysis_chamber.agents.nested import SESSION_ENV


def role_options(
    ctx: RunContext, role: str, system_prompt: SystemPromptPreset, **fields: Any
) -> ClaudeAgentOptions:
    """Options for one chamber role.

    Args:
        ctx: The run.
        role: "lead", "critic" or "qa"; picks the model (`<role>_model`) and
            security's disallowed list.
        system_prompt: The role's prompt preset.
        **fields: Role-specific ClaudeAgentOptions fields (mcp_servers, hooks,
            resume). `hooks` defaults to security.build_hooks(ctx, role).

    Returns:
        The options.

    Raises:
        ValueError: An unknown role (from security.disallowed_tools).
    """
    defaults: dict[str, Any] = {
        "model": getattr(ctx.config, f"{role}_model"),
        "cwd": str(ctx.run_dir),
        "permission_mode": "bypassPermissions",
        "disallowed_tools": security.disallowed_tools(role),
        "setting_sources": [],
        "strict_mcp_config": True,
        "mcp_servers": {},
        "system_prompt": system_prompt,
        "add_dirs": [str(ctx.config.playbook_path)],
        "env": kit.run_env(ctx.run_dir, ctx.config) | SESSION_ENV,
    }
    if "hooks" not in fields:
        defaults["hooks"] = security.build_hooks(ctx, role)
    return ClaudeAgentOptions(**(defaults | fields))
