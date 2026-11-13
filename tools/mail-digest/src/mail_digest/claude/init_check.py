"""Checks claude's stream-json `init` event against the lockdown the command asked for.

The init event is printed before the model's first turn and lists the permission
mode, the tools, the MCP servers and the folders claude actually loaded. If a Claude
Code update changes how a flag behaves, this is where the runner notices, and the
launcher kills the run before the model can act.
"""

import os
from pathlib import Path

from mail_digest.claude.lockdown import DIGEST_LOCKDOWN, EXPECTED_PERMISSION_MODE, Lockdown


def init_problems(event: dict, cwd: Path, lockdown: Lockdown = DIGEST_LOCKDOWN) -> list[str]:
    """How the init event differs from the expected lockdown ([] if it matches).

    cwd is the folder the runner started claude in (life/ for the digest): --restricted
    confines the file tools to it, so claude must report it, and no additional
    directories. lockdown says which tools and MCP servers it must list, exactly.
    """
    problems = []
    mode = event.get("permissionMode")
    if mode != EXPECTED_PERMISSION_MODE:
        problems.append(f"permissionMode is {mode!r}")
    tools = event.get("tools")
    is_str_list = isinstance(tools, list) and all(isinstance(t, str) for t in tools)
    if not is_str_list or set(tools) != lockdown.expected_tools:
        problems.append(f"tools are {tools!r}")
    servers = event.get("mcp_servers")
    if _server_states(servers) != list(lockdown.expected_mcp_servers):
        problems.append(f"mcp_servers are {servers!r}")
    # Older versions may leave the key out; when it's there it must be empty.
    extra_dirs = event.get("additional_directories", [])
    if extra_dirs != []:
        problems.append(f"additional_directories are {extra_dirs!r}")
    if not _is_same_folder(event.get("cwd"), cwd):
        problems.append(f"cwd is {event.get('cwd')!r}")
    return problems


def _server_states(servers: object) -> list[dict] | None:
    """Just the name and status of each MCP server entry, or None if malformed."""
    if not isinstance(servers, list) or not all(isinstance(s, dict) for s in servers):
        return None
    return [{"name": s.get("name"), "status": s.get("status")} for s in servers]


def _is_same_folder(reported: object, cwd: Path) -> bool:
    """True if claude's reported cwd is cwd (links resolved, case ignored on Windows)."""
    if not isinstance(reported, str) or not reported:
        return False
    return os.path.normcase(os.path.realpath(reported)) == os.path.normcase(os.path.realpath(cwd))
