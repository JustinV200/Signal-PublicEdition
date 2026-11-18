"""Wiring: turn finished tools into Claude Code config (MCP servers, permissions, hooks).

Public API: build_plan, apply_plan, summary_lines, wired_tools (read-only: which finished
tools are already in the config), WiringError, check_object, and the small edits setup makes.
"""

from pathlib import Path

from signal_setup.registry import Tool
from signal_setup.wiring.edits import EMAIL_PATTERN, set_constant, set_env_value
from signal_setup.wiring.json_file import WiringError, check_object
from signal_setup.wiring.plan import Plan
from signal_setup.wiring.plan import build as build_plan
from signal_setup.wiring.present import wired_tools
from signal_setup.wiring.writers import (
    MCP_FILE,
    SETTINGS_FILE,
    write_mcp,
    write_settings,
    write_statusline,
)

USER_SETTINGS = Path.home() / ".claude" / "settings.json"

__all__ = [
    "EMAIL_PATTERN",
    "Plan",
    "WiringError",
    "apply_plan",
    "build_plan",
    "check_object",
    "set_constant",
    "set_env_value",
    "summary_lines",
    "wired_tools",
]


def summary_lines(plan: Plan) -> list[str]:
    """The consent summary shown before the one confirmation.

    First the plain lines (one per tool: what Claude may do without asking), then one
    blank line, then the exact entries. The setup window splits at that blank line and
    folds the exact entries under Show exact entries.
    """
    # Not "everything else asks": the owner's own settings (a permission mode such as
    # bypassPermissions included) are kept, and scheduled runs set their own flags.
    kept = "Your own permission settings, mode included, stay as they are."
    if plan.consent:
        plain = [*plan.consent, f"Setup auto-approves nothing else. {kept}"]
    else:
        plain = [f"No tool is finished yet, so setup adds nothing. {kept}"]
    return [*plain, "", *_exact_lines(plan)]


def _exact_lines(plan: Plan) -> list[str]:
    """Every server, allow rule and hook the plan writes, and the files they go in."""
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
    return lines


def apply_plan(root: Path, tools: tuple[Tool, ...], plan: Plan, platform: str) -> list[str]:
    """Write the plan. Returns notes for the user (e.g. a status line that was kept).

    Raises WiringError, with one sentence for the user, when a file can't be safely
    rewritten; that file is left as it was. A file that isn't a JSON object is refused
    before any file is written, so that refusal changes nothing.
    """
    targets = [root / MCP_FILE, root / SETTINGS_FILE, *([USER_SETTINGS] if plan.statusline else [])]
    for path in targets:
        check_object(path)
    write_mcp(root, tools, plan)
    write_settings(root, tools, plan, platform)
    notes = []
    if plan.statusline and not write_statusline(root, USER_SETTINGS, platform):
        notes.append(f"Kept your own status line in {USER_SETTINGS}; see tools/usage/README.md.")
    return notes
