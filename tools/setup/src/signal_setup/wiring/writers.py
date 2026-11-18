"""Writes a Plan into .mcp.json, .claude/settings.local.json and the user's status line.

Each writer merges: entries the user added themselves are kept, entries setup owns are
replaced by the current plan, so a tool skipped on a re-run loses its wiring. Setup never
writes a permission mode (and never bypassPermissions). Every file goes through
json_file.update_json_file, which refuses a file that isn't a JSON object, backs the old
one up to .setup/backups/ and replaces it atomically.
"""

import json
from pathlib import Path
from typing import Any

from signal_setup.platforms import venv_python
from signal_setup.registry import Tool
from signal_setup.wiring.edits import ensure_env_file
from signal_setup.wiring.json_file import update_json_file
from signal_setup.wiring.plan import Plan, hook_entry, owned

MCP_EXAMPLE = Path(".mcp.example.json")
MCP_FILE = Path(".mcp.json")
SETTINGS_FILE = Path(".claude") / "settings.local.json"
STATUSLINE_MODULE = "usage.statusline"
# Each file's copy from before setup's last write to it (gitignored with the rest of .setup/).
BACKUP_DIR = Path(".setup") / "backups"
MCP_BACKUP = "mcp.json"
SETTINGS_BACKUP = "settings.local.json"
USER_SETTINGS_BACKUP = "user-settings.json"


def write_mcp(root: Path, tools: tuple[Tool, ...], plan: Plan) -> None:
    """Write .mcp.json: the plan's servers (from .mcp.example.json) plus the user's own.

    Raises WiringError (see update_json_file) when .mcp.json can't be safely rewritten.
    """
    example = json.loads((root / MCP_EXAMPLE).read_text("utf-8"))["mcpServers"]
    owned_servers = owned(tools)[0]

    def merge(config: dict[str, Any]) -> dict[str, Any]:
        current = config.get("mcpServers", {})
        servers = {k: v for k, v in current.items() if k not in owned_servers}
        servers.update({name: example[name] for name in plan.mcp_servers})
        return {**config, "mcpServers": servers}  # other top-level keys stay

    if plan.mcp_servers:
        ensure_env_file(root)  # every server runs `uv run --env-file .env`
    update_json_file(root / MCP_FILE, root / BACKUP_DIR / MCP_BACKUP, merge)


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
    """Merge the plan into .claude/settings.local.json.

    Raises WiringError (see update_json_file) when the file can't be safely rewritten.
    """
    update_json_file(
        root / SETTINGS_FILE,
        root / BACKUP_DIR / SETTINGS_BACKUP,
        lambda settings: merge_settings(settings, root, tools, plan, platform),
    )


def _with_statusline(settings: dict[str, Any], command: str) -> dict[str, Any]:
    """`settings` pointing at usage's status line, unless it names a different one.

    Never changes `settings` itself: a change comes back as a new dict.
    """
    existing = settings.get("statusLine", {}).get("command", "")
    if not existing or STATUSLINE_MODULE in existing:
        statusline = {"type": "command", "command": command, "refreshInterval": 30}
        return {**settings, "statusLine": statusline}
    return settings


def write_statusline(root: Path, user_settings: Path, platform: str) -> bool:
    """Point the user's status line at usage's, unless they already have a different one.

    Returns True if written (or already ours), False if another status line was kept.
    Raises WiringError (see update_json_file) when the file can't be safely rewritten.
    """
    command = f"{venv_python(root, 'usage', platform)} -I -m {STATUSLINE_MODULE}"
    saved = update_json_file(
        user_settings,
        root / BACKUP_DIR / USER_SETTINGS_BACKUP,
        lambda settings: _with_statusline(settings, command),
    )
    return saved.get("statusLine", {}).get("command") == command
