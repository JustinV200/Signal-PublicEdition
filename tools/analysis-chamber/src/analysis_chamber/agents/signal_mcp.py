"""Signal's MCP servers for a chamber role, loaded from the repo's .mcp.json.

.mcp.json launches every server with `uv run` and repo-relative paths
(`--project packages/mcpshim`, inner `--env-file .env --project tools/mail`).
From a run folder those don't resolve and every server fails (spike
notes, not published). Adding `--directory <repo_root>` to the outer
`uv run` makes uv resolve them against the repo and start the shim there, so
the inner command's relative paths resolve too. The spike verified that rewrite.
"""

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

MCP_CONFIG_NAME = ".mcp.json"


def load_signal_servers(repo_root: Path, wanted: set[str]) -> dict[str, dict[str, Any]]:
    """The named Signal MCP servers, launchable from any cwd.

    Callers pass security.mcp_servers_for(role), so a role never even sees the
    tools of a server its allowlist doesn't use.

    Args:
        repo_root: The Signal repo (holds .mcp.json).
        wanted: The server names (.mcp.json keys) to load.

    Returns:
        Server name -> stdio config. Names not in .mcp.json are skipped. Empty
        (with a logged warning) if .mcp.json is missing or unreadable, so a run
        still goes ahead without Signal reads.
    """
    if not wanted:
        return {}
    path = repo_root / MCP_CONFIG_NAME
    try:
        servers = json.loads(path.read_text(encoding="utf-8"))["mcpServers"]
    except (OSError, ValueError, KeyError, TypeError) as error:
        logger.warning("no Signal MCP servers for the lead: can't read %s: %s", path, error)
        return {}
    return {
        name: _launchable(server, repo_root) for name, server in servers.items() if name in wanted
    }


def _launchable(server: dict[str, Any], repo_root: Path) -> dict[str, Any]:
    """A copy of `server` whose outer `uv run` runs in repo_root; other commands unchanged."""
    args = list(server.get("args", []))
    if server.get("command") == "uv" and args[:1] == ["run"]:
        args = ["run", "--directory", str(repo_root), *args[1:]]
    return {**server, "type": "stdio", "args": args}
