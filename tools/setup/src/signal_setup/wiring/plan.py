"""What setup wires into Claude Code, worked out from the tools that are done.

Only finished tools (and their finished optional steps) contribute MCP servers,
permission rules, hooks and the status line. Skipped or unfinished tools get nothing.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from signal_setup import progress
from signal_setup.platforms import venv_python
from signal_setup.registry import Hook, Tool


@dataclass(frozen=True)
class Plan:
    """Everything setup would write, for the summary and for the writers."""

    tools: tuple[str, ...]
    mcp_servers: tuple[str, ...]
    allow: tuple[str, ...]
    hooks: tuple[tuple[str, Hook], ...]  # (tool id, hook)
    statusline: bool


def _done_step_extras(data: dict[str, Any], tool: Tool) -> tuple[list[str], list[str], bool]:
    """MCP servers, permissions and the status-line flag from the tool's finished steps."""
    servers: list[str] = []
    allow: list[str] = []
    statusline = False
    for step in tool.steps:
        if progress.step_status(data, tool.id, step.id) != progress.DONE:
            continue
        servers += step.mcp
        allow += step.permissions
        statusline = statusline or step.statusline
    return servers, allow, statusline


def _is_for_wired_server(rule: str, servers: list[str]) -> bool:
    """False for an `mcp__<server>` rule whose server isn't wired (a rule for nothing)."""
    if not rule.startswith("mcp__"):
        return True
    return rule.removeprefix("mcp__").split("__")[0] in servers


def build(tools: tuple[Tool, ...], data: dict[str, Any], platform: str) -> Plan:
    """The plan for every tool in `tools` whose status in `data` is done."""
    done = [t for t in tools if progress.tool_status(data, t, platform) == progress.DONE]
    servers: list[str] = []
    allow: list[str] = []
    hooks: list[tuple[str, Hook]] = []
    statusline = False
    for tool in done:
        extra_servers, extra_allow, wants_statusline = _done_step_extras(data, tool)
        servers += [*tool.mcp, *extra_servers]
        allow += [*tool.permissions, *extra_allow]
        hooks += [(tool.id, hook) for hook in tool.hooks]
        statusline = statusline or wants_statusline
    servers = list(dict.fromkeys(servers))
    allow = [rule for rule in dict.fromkeys(allow) if _is_for_wired_server(rule, servers)]
    return Plan(tuple(t.id for t in done), tuple(servers), tuple(allow), tuple(hooks), statusline)


def owned(tools: tuple[Tool, ...]) -> tuple[set[str], set[str], set[str]]:
    """Every server, allow rule and hook module setup could ever write (to replace on re-run)."""
    servers = {s for t in tools for s in (*t.mcp, *(m for st in t.steps for m in st.mcp))}
    allow = {r for t in tools for r in t.permissions}
    allow |= {r for t in tools for s in t.steps for r in s.permissions}
    modules = {h.module for t in tools for h in t.hooks}
    return servers, allow, modules


def hook_entry(root: Path, tool_id: str, hook: Hook, platform: str) -> dict[str, Any]:
    """The settings.json command hook for `hook`, run in exec form with the tool's venv Python."""
    args = ["-I", "-m", hook.module] if hook.isolated else ["-m", hook.module]
    entry: dict[str, Any] = {
        "type": "command",
        "command": venv_python(root, tool_id, platform),
        "args": args,
    }
    if hook.timeout:
        entry["timeout"] = hook.timeout
    if hook.is_async:
        entry["async"] = True
    return entry
