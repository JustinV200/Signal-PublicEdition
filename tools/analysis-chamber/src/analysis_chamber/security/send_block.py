"""The send block: layer 1 lists for ClaudeAgentOptions and the layer 2 PreToolUse hook.

Layer 1 is `disallowed_tools(role)`. Layer 2, send_block_hook, re-checks that list
(with the glob rules the CLI uses, so it also covers sub-agent calls) and then denies by
default: any mcp__ tool that isn't on the role's allowlist or the chamber's own server.
The hook also fires for sub-agent calls (spike, section 2), under the session's role.

The signup agent must be its own SDK session built with role "signup" (e.g. a nested
query() behind a chamber tool), not an AgentDefinition inside the lead: the lead's
layer 1 denies the whole browser server, and that deny applies to its sub-agents too.
"""

from typing import Any

from analysis_chamber.security.common import allow, deny
from analysis_chamber.security.rules.mcp_allowlists import (
    CHAMBER_SERVER_PREFIX,
    MCP_ALLOWLISTS,
)
from analysis_chamber.security.rules.tool_lists import (
    BUILTIN_DISALLOWED,
    OUTBOUND_TOOLS,
    ROLE_EXTRA_DISALLOWED,
    ROLES,
    SIGNAL_SERVER_TOOLS,
)

_MCP_PREFIX = "mcp__"
SIGNUP_ROLE = "signup"
_MAIL_PREFIX = "mcp__mail__"
_ACCOUNTLESS_MAIL_TOOLS = frozenset({"mcp__mail__mail_accounts"})


def _check_role(role: str) -> None:
    """Raise ValueError for a role this package doesn't know."""
    if role not in ROLES:
        raise ValueError(f"unknown chamber role {role!r}; expected one of {sorted(ROLES)}")


def _unallowed_server_tools(role: str) -> list[str]:
    """Signal MCP tools the role isn't allowed: whole servers, or the rest of a used one."""
    allowed = set(MCP_ALLOWLISTS[role])
    entries: list[str] = []
    for server, tools in SIGNAL_SERVER_TOOLS.items():
        names = [f"{_MCP_PREFIX}{server}__{tool}" for tool in tools]
        if allowed.isdisjoint(names):
            entries.append(_MCP_PREFIX + server)
        else:
            entries.extend(name for name in names if name not in allowed)
    return entries


def disallowed_tools(role: str) -> list[str]:
    """The `disallowed_tools` value for a chamber agent (layer 1).

    allowed_tools does nothing under bypassPermissions, so the allowlist is enforced
    here by listing everything else: built-ins, outbound tools, the role's extras, and
    every known Signal MCP tool not on its allowlist (whole servers where none is).

    Args:
        role: "lead", "critic", "qa" or "signup".

    Returns:
        A fresh, de-duplicated list of tool names, `mcp__server` names and `prefix*` globs.

    Raises:
        ValueError: on an unknown role.
    """
    _check_role(role)
    entries = [
        *BUILTIN_DISALLOWED,
        *ROLE_EXTRA_DISALLOWED[role],
        *OUTBOUND_TOOLS,
        *_unallowed_server_tools(role),
    ]
    return list(dict.fromkeys(entries))


def allowed_mcp_tools(role: str) -> list[str]:
    """The MCP tools a role may call, besides the chamber's own mcp__chamber__* tools.

    Raises:
        ValueError: on an unknown role.
    """
    _check_role(role)
    return list(MCP_ALLOWLISTS[role])


def mcp_servers_for(role: str) -> set[str]:
    """The Signal MCP server names (.mcp.json keys) a role's allowlist needs loaded."""
    return {name.split("__")[1] for name in allowed_mcp_tools(role)}


def matches_entry(tool_name: str, entry: str) -> bool:
    """Whether a disallowed_tools entry covers a tool name.

    Entries are an exact name, a bare `mcp__server` (the whole server), or a
    trailing-`*` prefix glob, the forms the tool-isolation spike verified.
    """
    if entry.endswith("*"):
        return tool_name.startswith(entry[:-1])
    if tool_name == entry:
        return True
    # A bare server entry has exactly one `__` (mcp__name) and covers its tools.
    is_server_entry = entry.startswith(_MCP_PREFIX) and entry.count("__") == 1
    return is_server_entry and tool_name.startswith(entry + "__")


def block_reason(
    role: str, tool_name: str, tool_input: dict[str, Any], signup_account: str = ""
) -> str | None:
    """Why a role may not make this call, or None when it may.

    signup_account is the one mailbox the signup role may read; "" means none.

    Raises:
        ValueError: on an unknown role.
    """
    if any(matches_entry(tool_name, entry) for entry in disallowed_tools(role)):
        return f"{tool_name} is blocked for chamber runs (no sends, posts, deletes or raw web)."
    if not tool_name.startswith(_MCP_PREFIX) or tool_name.startswith(CHAMBER_SERVER_PREFIX):
        return None
    if tool_name not in MCP_ALLOWLISTS[role]:
        return f"{tool_name} is not on the {role} role's read-only MCP allowlist."
    is_scoped_mail = tool_name.startswith(_MAIL_PREFIX) and tool_name not in _ACCOUNTLESS_MAIL_TOOLS
    if role == SIGNUP_ROLE and is_scoped_mail:
        account = str(tool_input.get("account", "")).lower()
        if not signup_account or account != signup_account.lower():
            return "The signup agent may only read the configured signup mail account."
    return None


async def send_block_hook(
    hook_input: dict[str, Any],
    tool_use_id: str | None,
    context: Any,
    *,
    role: str,
    signup_account: str = "",
) -> dict[str, Any]:
    """PreToolUse hook (SDK HookCallback signature, `role` bound by build_hooks).

    Args:
        hook_input: The SDK's PreToolUseHookInput (`tool_name`, `tool_input`).
        tool_use_id: Unused.
        context: Unused (SDK HookContext).
        role: The session's role.
        signup_account: The mailbox the signup role may read ("" = none).

    Returns:
        A deny output for blocked calls, else an empty output.
    """
    tool_name = str(hook_input.get("tool_name", ""))
    reason = block_reason(role, tool_name, hook_input.get("tool_input") or {}, signup_account)
    if reason is None:
        return allow()
    return deny(reason + " Write results into the run folder; the daemon notifies the user.")
