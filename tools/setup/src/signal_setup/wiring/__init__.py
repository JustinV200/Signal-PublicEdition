"""Wiring: turn finished tools into Claude Code config (MCP servers, permissions, hooks).

Public API: build_plan, apply_plan, summary_lines, and the small edits setup makes.
"""

from pathlib import Path

from signal_setup.registry import Tool
from signal_setup.wiring.edits import EMAIL_PATTERN, set_constant, set_env_value
from signal_setup.wiring.plan import Plan
from signal_setup.wiring.plan import build as build_plan
from signal_setup.wiring.writers import write_mcp, write_settings, write_statusline

USER_SETTINGS = Path.home() / ".claude" / "settings.json"

__all__ = [
    "EMAIL_PATTERN",
    "Plan",
    "apply_plan",
    "build_plan",
    "set_constant",
    "set_env_value",
    "summary_lines",
]


def summary_lines(plan: Plan) -> list[str]:
    """The permissions summary shown before the one confirmation."""
    hooks = sorted({f"{h.event}: {tool} ({h.module})" for tool, h in plan.hooks})
    lines = [
        f"Tools to wire: {', '.join(plan.tools) or 'none'}",
        f"MCP servers (.mcp.json): {', '.join(plan.mcp_servers) or 'none'}",
        "Auto-approved in Claude Code (.claude/settings.local.json):",
    ]
    lines += [f"  {rule}" for rule in plan.allow] or ["  nothing"]
    lines += ["Hooks (.claude/settings.local.json):"] + ([f"  {h}" for h in hooks] or ["  none"])
    if plan.statusline:
        lines.append(f"Status line: usage's, in {USER_SETTINGS}")
    lines.append("Everything else still asks first. No permission mode is changed.")
    return lines


def apply_plan(root: Path, tools: tuple[Tool, ...], plan: Plan, platform: str) -> list[str]:
    """Write the plan. Returns notes for the user (e.g. a status line that was kept)."""
    write_mcp(root, tools, plan)
    write_settings(root, tools, plan, platform)
    notes = []
    if plan.statusline and not write_statusline(root, USER_SETTINGS, platform):
        notes.append(f"Kept your own status line in {USER_SETTINGS}; see tools/usage/README.md.")
    return notes
