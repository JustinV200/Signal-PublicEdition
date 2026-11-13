"""Writes a Plan into .mcp.json, .claude/settings.local.json and the user's status line.

Each writer merges: entries the user added themselves are kept, entries setup owns are
replaced by the current plan, so a tool skipped on a re-run loses its wiring. Setup never
writes a permission mode (and never bypassPermissions).
"""

import json
from pathlib import Path
from typing import Any

from signal_setup.platforms import venv_python
from signal_setup.registry import Tool
from signal_setup.wiring.edits import ensure_env_file
from signal_setup.wiring.plan import Plan, hook_entry, owned

MCP_EXAMPLE = Path(".mcp.example.json")
MCP_FILE = Path(".mcp.json")
SETTINGS_FILE = Path(".claude") / "settings.local.json"
STATUSLINE_MODULE = "usage.statusline"


def _load_json(path: Path) -> dict[str, Any]:
    """The JSON object in `path`, or {} if the file doesn't exist."""
    return json.loads(path.read_text("utf-8")) if path.exists() else {}


def _dump_json(path: Path, data: dict[str, Any]) -> None:
    """Write `data` as indented JSON, creating the folder."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", "utf-8")


def write_mcp(root: Path, tools: tuple[Tool, ...], plan: Plan) -> None:
    """Write .mcp.json: the plan's servers (from .mcp.example.json) plus the user's own."""
    example = _load_json(root / MCP_EXAMPLE)["mcpServers"]
    owned_servers = owned(tools)[0]
    current = _load_json(root / MCP_FILE).get("mcpServers", {})
    servers = {k: v for k, v in current.items() if k not in owned_servers}
    servers.update({name: example[name] for name in plan.mcp_servers})
    if plan.mcp_servers:
        ensure_env_file(root)  # every server runs `uv run --env-file .env`
    _dump_json(root / MCP_FILE, {"mcpServers": servers})


def _is_owned_group(group: dict[str, Any], modules: set[str]) -> bool:
    """True if a hook group runs one of setup's hook modules."""
    return any(set(h.get("args", [])) & modules for h in group.get("hooks", []))


def _merge_hooks(
    settings: dict[str, Any], root: Path, plan: Plan, modules: set[str], platform: str
) -> None:
    """Drop setup's old hook groups from `settings`, then add the plan's."""
    hooks = settings.setdefault("hooks", {})
    for event in list(hooks):
        hooks[event] = [g for g in hooks[event] if not _is_owned_group(g, modules)]
    for tool_id, hook in plan.hooks:
        group: dict[str, Any] = {"hooks": [hook_entry(root, tool_id, hook, platform)]}
        if hook.matcher:
            group = {"matcher": hook.matcher, **group}
        hooks.setdefault(hook.event, []).append(group)
    settings["hooks"] = {event: groups for event, groups in hooks.items() if groups}
    if not settings["hooks"]:
        del settings["hooks"]


def merge_settings(
    settings: dict[str, Any], root: Path, tools: tuple[Tool, ...], plan: Plan, platform: str
) -> dict[str, Any]:
    """`settings` with setup's permissions, MCP approvals and hooks replaced by the plan's."""
    owned_servers, owned_allow, modules = owned(tools)
    permissions = settings.setdefault("permissions", {})
    kept = [rule for rule in permissions.get("allow", []) if rule not in owned_allow]
    permissions["allow"] = kept + list(plan.allow)
    enabled = [s for s in settings.get("enabledMcpjsonServers", []) if s not in owned_servers]
    settings["enabledMcpjsonServers"] = enabled + list(plan.mcp_servers)
    _merge_hooks(settings, root, plan, modules, platform)
    return settings


def write_settings(root: Path, tools: tuple[Tool, ...], plan: Plan, platform: str) -> None:
    """Merge the plan into .claude/settings.local.json."""
    path = root / SETTINGS_FILE
    _dump_json(path, merge_settings(_load_json(path), root, tools, plan, platform))


def write_statusline(root: Path, user_settings: Path, platform: str) -> bool:
    """Point the user's status line at usage's, unless they already have a different one.

    Returns True if written (or already ours), False if another status line was kept.
    """
    command = f"{venv_python(root, 'usage', platform)} -I -m {STATUSLINE_MODULE}"
    settings = _load_json(user_settings)
    existing = settings.get("statusLine", {}).get("command", "")
    if existing and STATUSLINE_MODULE not in existing:
        return False
    settings["statusLine"] = {"type": "command", "command": command, "refreshInterval": 30}
    _dump_json(user_settings, settings)
    return True
