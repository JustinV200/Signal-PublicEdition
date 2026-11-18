"""Which finished tools are already in Claude Code's config, worked out by reading only.

`setup list` and `setup status --json` report it as `wired`, so the setup window can say
"Set up, not added to Claude Code yet" instead of Active. A finished tool is wired when
everything `wire` would add for it that makes it load is there: its MCP servers in
.mcp.json, and its hook modules in .claude/settings.local.json or the checked-in
.claude/settings.json. A server in .mcp.json counts even when enabledMcpjsonServers
lacks it: Claude Code then asks once to approve it. Allow rules don't count: without
them the tool still loads and only asks first. Nothing here writes a file.
"""

import json
from pathlib import Path
from typing import Any

from signal_setup.registry import Tool
from signal_setup.wiring.plan import build
from signal_setup.wiring.writers import MCP_FILE, SETTINGS_FILE

# Claude Code's checked-in project settings, where a hook can be wired by hand.
PROJECT_SETTINGS_FILE = Path(".claude") / "settings.json"


def _read_object(path: Path) -> dict[str, Any]:
    """The JSON object in `path`, or {} when it's missing, unreadable or not an object.

    A broken file counts as empty on purpose: Claude Code can't load tools from it either,
    so nothing in it is wired.
    """
    try:
        data = json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _dicts(value: Any) -> list[dict[str, Any]]:
    """The dicts in `value` when it's a list ([] otherwise): hand-edited files can hold anything."""
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _hook_modules(settings: dict[str, Any]) -> set[str]:
    """Every argument of every command hook in `settings` (setup's hooks run `-m <module>`).

    Matched by module, not (event, module), the same way `wire` decides what it owns
    (`writers._is_owned_group`): a module wired for only some of its events still counts.
    """
    events = settings.get("hooks")
    if not isinstance(events, dict):
        return set()
    groups = [group for value in events.values() for group in _dicts(value)]
    hooks = [hook for group in groups for hook in _dicts(group.get("hooks"))]
    return {arg for hook in hooks for arg in hook.get("args", []) if isinstance(arg, str)}


def wired_tools(
    root: Path, tools: tuple[Tool, ...], data: dict[str, Any], platform: str
) -> set[str]:
    """Ids of the finished tools whose servers and hooks are all in Claude Code's config.

    Args:
        root: The repo root.
        tools: The registry tools to check.
        data: The saved progress (which tools and optional steps are done).
        platform: The current platform.

    Returns:
        The ids of the wired tools. A tool that isn't done is never in it.
    """
    servers = _read_object(root / MCP_FILE).get("mcpServers")
    servers = set(servers) if isinstance(servers, dict) else set()
    modules = _hook_modules(_read_object(root / SETTINGS_FILE))
    modules |= _hook_modules(_read_object(root / PROJECT_SETTINGS_FILE))
    wired = set()
    for tool in tools:
        plan = build((tool,), data, platform)
        if not plan.tools:
            continue  # not done: nothing to wire yet, so not wired
        hook_modules = {hook.module for _, hook in plan.hooks}
        if set(plan.mcp_servers) <= servers and hook_modules <= modules:
            wired.add(tool.id)
    return wired
