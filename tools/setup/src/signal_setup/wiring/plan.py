"""What setup wires into Claude Code, worked out from the tools that are done.

Only finished tools (and their finished optional steps) contribute MCP servers,
permission rules, hooks and the status line, each with one plain consent line saying
what that lets Claude do. Skipped or unfinished tools get nothing.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any, NamedTuple

from signal_setup import progress
from signal_setup.platforms import venv_python
from signal_setup.registry import Hook, Tool
from signal_setup.wiring.consent import Grants, consent_line


@dataclass(frozen=True)
class Plan:
    """Everything setup would write, for the summary and for the writers."""

    tools: tuple[str, ...]
    mcp_servers: tuple[str, ...]
    allow: tuple[str, ...]
    hooks: tuple[tuple[str, Hook], ...]  # (tool id, hook)
    statusline: bool
    # One plain line per tool, for the consent page (consent.consent_line).
    consent: tuple[str, ...] = ()


class _Adds(NamedTuple):
    """What one finished tool adds: its MCP servers, allow rules and two step flags."""

    servers: list[str]
    allow: list[str]
    statusline: bool
    runs_claude: bool  # a done step registers an unattended Claude run


def _adds(data: dict[str, Any], tool: Tool) -> _Adds:
    """The tool's own servers and rules, plus those of its finished steps."""
    servers, allow = list(tool.mcp), list(tool.permissions)
    statusline = runs_claude = False
    for step in tool.steps:
        if progress.step_status(data, tool.id, step.id) != progress.DONE:
            continue
        servers += step.mcp
        allow += step.permissions
        statusline = statusline or step.statusline
        runs_claude = runs_claude or step.unattended_claude
    return _Adds(servers, allow, statusline, runs_claude)


def _grants(adds: _Adds, allowed: list[str]) -> Grants:
    """The consent page's view of a tool: its filtered rules and what its steps set up."""
    return Grants(allowed, bool(adds.servers), adds.statusline, adds.runs_claude)


def _is_for_wired_server(rule: str, servers: list[str]) -> bool:
    """False for an `mcp__<server>` rule whose server isn't wired (a rule for nothing)."""
    if not rule.startswith("mcp__"):
        return True
    return rule.removeprefix("mcp__").split("__")[0] in servers


def build(tools: tuple[Tool, ...], data: dict[str, Any], platform: str) -> Plan:
    """The plan for every tool in `tools` whose status in `data` is done."""
    done = [t for t in tools if progress.tool_status(data, t, platform) == progress.DONE]
    adds = {t.id: _adds(data, t) for t in done}
    servers = list(dict.fromkeys(s for t in done for s in adds[t.id].servers))
    # Each tool's rules, less those for a server nobody wires (they'd be rules for nothing).
    allowed = {
        t.id: [r for r in dict.fromkeys(adds[t.id].allow) if _is_for_wired_server(r, servers)]
        for t in done
    }
    return Plan(
        tools=tuple(t.id for t in done),
        mcp_servers=tuple(servers),
        allow=tuple(dict.fromkeys(r for t in done for r in allowed[t.id])),
        hooks=tuple((t.id, hook) for t in done for hook in t.hooks),
        statusline=any(adds[t.id].statusline for t in done),
        consent=tuple(consent_line(t, _grants(adds[t.id], allowed[t.id])) for t in done),
    )


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
