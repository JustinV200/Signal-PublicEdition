"""Writes a Plan into .mcp.json, .claude/settings.local.json and the user's status line.

Each writer merges by the ledger (ledger.py, merge.py): an entry is setup's only when
setup's own ledger lists it and the file still holds it as recorded. Those are swapped
for the current plan's, so a tool skipped on a re-run loses what setup added for it.
Every other entry stays exactly as it is, and where the plan wants one the file already
has (a server of that name, a hook on that event for that module), the one there is left
alone and not taken over. Each writer returns the ledger as it now stands. Setup never
writes a permission mode (and never bypassPermissions). Every file goes through
json_file.update_json_file, which refuses a file that isn't a JSON object, backs the old
one up to .setup/backups/ and replaces it atomically.
"""

import json
from dataclasses import replace
from pathlib import Path
from typing import Any

from signal_setup.platforms import venv_python
from signal_setup.wiring.edits import ensure_env_file
from signal_setup.wiring.json_file import WiringError, read_object, update_json_file
from signal_setup.wiring.ledger import Ledger
from signal_setup.wiring.merge import hook_args, merge_hooks, merge_listed, merge_named
from signal_setup.wiring.plan import Plan, hook_entry

MCP_EXAMPLE = Path(".mcp.example.json")
MCP_FILE = Path(".mcp.json")
SETTINGS_FILE = Path(".claude") / "settings.local.json"
# Claude Code's checked-in project settings, where a hook can be wired by hand.
PROJECT_SETTINGS_FILE = Path(".claude") / "settings.json"
ENABLED_KEY = "enabledMcpjsonServers"
STATUSLINE_MODULE = "usage.statusline"
# Each file's copy from before setup's last write to it (gitignored with the rest of .setup/).
BACKUP_DIR = Path(".setup") / "backups"
MCP_BACKUP = "mcp.json"
SETTINGS_BACKUP = "settings.local.json"
USER_SETTINGS_BACKUP = "user-settings.json"


def _section(container: dict[str, Any], key: str, kind: type, path: Path) -> Any:
    """`container[key]`, or an empty `kind` when the key is absent.

    Raises:
        WiringError: The key holds something else, which setup can't merge into.
    """
    value = container.get(key, kind())
    if not isinstance(value, kind):
        what = "an object" if kind is dict else "a list"
        raise WiringError(f"{key!r} in {path} isn't {what}, so setup left the file alone.")
    return value


def _put(container: dict[str, Any], key: str, value: Any) -> None:
    """Set `container[key]`, unless that would only add an empty entry the file didn't have."""
    if value or key in container:
        container[key] = value


def write_mcp(root: Path, plan: Plan, added: Ledger) -> Ledger:
    """Merge the plan's servers (from .mcp.example.json) into .mcp.json.

    Returns `added` with the servers that are setup's now.
    Raises WiringError (see update_json_file) when .mcp.json can't be safely rewritten.
    """
    path = root / MCP_FILE
    example = json.loads((root / MCP_EXAMPLE).read_text("utf-8"))["mcpServers"]
    wanted = {name: example[name] for name in plan.mcp_servers}
    owned: dict[str, Any] = {}

    def merge(config: dict[str, Any]) -> dict[str, Any]:
        nonlocal owned
        current = _section(config, "mcpServers", dict, path)
        servers, owned = merge_named(current, added.servers, wanted)
        _put(config, "mcpServers", servers)  # other top-level keys stay
        return config

    if plan.mcp_servers:
        ensure_env_file(root)  # every server runs `uv run --env-file .env`
    update_json_file(path, root / BACKUP_DIR / MCP_BACKUP, merge)
    return replace(added, servers=owned)


def _wanted_hooks(root: Path, plan: Plan, platform: str) -> list[tuple[str, dict[str, Any]]]:
    """(module, ledger record) for each hook of the plan, as merge_hooks takes them."""
    return [
        (
            hook.module,
            {
                "event": hook.event,
                "matcher": hook.matcher,
                "hook": hook_entry(root, tool_id, hook, platform),
            },
        )
        for tool_id, hook in plan.hooks
    ]


def write_settings(root: Path, plan: Plan, added: Ledger, platform: str) -> Ledger:
    """Merge the plan's allow rules, MCP approvals and hooks into .claude/settings.local.json.

    A hook already in the checked-in .claude/settings.json counts as there, so it isn't
    added a second time (it would run twice).

    Returns `added` with the rules, approvals and hooks that are setup's now.
    Raises WiringError (see update_json_file) when the file can't be safely rewritten.
    """
    path = root / SETTINGS_FILE
    wanted_hooks = _wanted_hooks(root, plan, platform)
    elsewhere = hook_args(read_object(root / PROJECT_SETTINGS_FILE).get("hooks"))
    owned = added

    def merge(settings: dict[str, Any]) -> dict[str, Any]:
        nonlocal owned
        permissions = _section(settings, "permissions", dict, path)
        current_allow = _section(permissions, "allow", list, path)
        allow, owned_allow = merge_listed(current_allow, added.allow, list(plan.allow))
        _put(permissions, "allow", allow)
        _put(settings, "permissions", permissions)
        current_enabled = _section(settings, ENABLED_KEY, list, path)
        enabled, owned_enabled = merge_listed(
            current_enabled, added.enabled, list(plan.mcp_servers)
        )
        _put(settings, ENABLED_KEY, enabled)
        events = _section(settings, "hooks", dict, path)
        for _, record in wanted_hooks:
            _section(events, record["event"], list, path)
        owned_hooks = merge_hooks(events, added.hooks, wanted_hooks, elsewhere)
        _put(settings, "hooks", events)
        owned = replace(added, allow=owned_allow, enabled=owned_enabled, hooks=owned_hooks)
        return settings

    update_json_file(path, root / BACKUP_DIR / SETTINGS_BACKUP, merge)
    return owned


def write_statusline(
    root: Path, user_settings: Path, platform: str, added: Ledger
) -> tuple[Ledger, bool]:
    """Point the user's status line at usage's, unless they have one setup didn't write.

    Written when there is none, or the one there is still the one the ledger says setup
    wrote. Any other is kept as it is, usage's own module or not.

    Returns:
        `added` with the status line that is setup's now (None when another was kept), and
        whether the one in place runs usage's command.

    Raises:
        WiringError: The file can't be safely rewritten (see update_json_file).
    """
    command = f"{venv_python(root, 'usage', platform)} -I -m {STATUSLINE_MODULE}"
    wanted = {"type": "command", "command": command, "refreshInterval": 30}
    owned: dict[str, Any] | None = None

    def merge(settings: dict[str, Any]) -> dict[str, Any]:
        nonlocal owned
        existing = settings.get("statusLine")
        owned = None if existing and existing != added.statusline else wanted
        return {**settings, "statusLine": wanted} if owned else settings

    saved = update_json_file(user_settings, root / BACKUP_DIR / USER_SETTINGS_BACKUP, merge)
    status_line = saved.get("statusLine")
    is_usage = isinstance(status_line, dict) and status_line.get("command") == command
    return replace(added, statusline=owned), is_usage
