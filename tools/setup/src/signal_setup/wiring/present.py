"""Which finished tools are already in Claude Code's config, worked out by reading only.

`setup list` and `setup status --json` report it as `wired`, so the setup window can say
"Set up, not added to Claude Code yet" instead of Active. A finished tool is wired when
everything `wire` would add for it that makes it load is there: its MCP servers in
.mcp.json, and its hook modules in .claude/settings.local.json or the checked-in
.claude/settings.json. A server in .mcp.json counts even when enabledMcpjsonServers
lacks it: Claude Code then asks once to approve it. Allow rules don't count: without
them the tool still loads and only asks first. Nothing here writes a file.
"""

from pathlib import Path
from typing import Any

from signal_setup.registry import Tool
from signal_setup.wiring.json_file import read_object
from signal_setup.wiring.merge import hook_args
from signal_setup.wiring.plan import build
from signal_setup.wiring.writers import MCP_FILE, PROJECT_SETTINGS_FILE, SETTINGS_FILE


def _hook_modules(root: Path) -> set[str]:
    """Every argument of every command hook in either settings file (setup's run `-m <module>`).

    Matched by module, not (event, module): a module wired for only some of its events
    still counts.
    """
    files = (SETTINGS_FILE, PROJECT_SETTINGS_FILE)
    return {arg for file in files for _, arg in hook_args(read_object(root / file).get("hooks"))}


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
    servers = read_object(root / MCP_FILE).get("mcpServers")
    servers = set(servers) if isinstance(servers, dict) else set()
    modules = _hook_modules(root)
    wired = set()
    for tool in tools:
        plan = build((tool,), data, platform)
        if not plan.tools:
            continue  # not done: nothing to wire yet, so not wired
        hook_modules = {hook.module for _, hook in plan.hooks}
        if set(plan.mcp_servers) <= servers and hook_modules <= modules:
            wired.add(tool.id)
    return wired
