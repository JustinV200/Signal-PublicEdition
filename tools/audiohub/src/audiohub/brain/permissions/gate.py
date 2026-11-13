"""The voice permission gate: decides whether a tool call Claude wants to make may run.

Voice is a thin, fast layer: music, the whiteboard, the brief, sleep mode,
quick lookups. Everything else is the main Signal session's job. So the gate
never asks a question. A call runs silently when:
- its tool is named exactly in `auto_allow_tools` (Read, Glob, Grep, WebSearch,
  the read-only mail and sessions tools, and the brief but for brief_log and
  brief_undo, by default), or belongs to a server named in
  `auto_allow_mcp_servers` (audiohub, whiteboard, sleepmode);
- it is the hand-off to the main session (always, whatever the config says).
Any other call is refused quietly, and Claude is told to hand the job off.
A Read, Glob or Grep of a secret is refused too (secret_paths.py). Every tool
call reaches this gate, because sdk_options.py's PreToolUse hook makes the CLI
ask about each one. This module knows nothing about the SDK.
"""

import logging
import re
from collections.abc import Awaitable, Callable, Collection, Mapping
from dataclasses import dataclass
from pathlib import Path

from audiohub.brain.handoff_tool import HAND_OFF_TOOL, HAND_OFF_TOOL_NAME
from audiohub.brain.permissions.secret_paths import SECRET_READ_REFUSAL, targets_secret
from audiohub.brain.permissions.tool_paths import resolve_path, target_paths

logger = logging.getLogger(__name__)

# The CLI names MCP tools "mcp__<server>__<tool>", so a server called "audiohub__x"
# or "audiohub_" produces names that also start with "mcp__audiohub__". The owner's
# tool names are snake_case words without a double or leading underscore, so
# requiring an exact server name and exactly that shape after it rejects those
# look-alike servers.
_MCP_TOOL_PREFIX = "mcp__{server}__"
_MCP_TOOL_NAME = re.compile(r"[A-Za-z0-9-]+(?:_[A-Za-z0-9-]+)*")

# Tools whose paths are checked for secrets.
READ_ONLY_TOOLS = frozenset({"Read", "Glob", "Grep"})

# Always allowed: the hand-off only passes a job, with the owner's own words, to
# the main session, which judges it there.
ALWAYS_ALLOWED_TOOLS = frozenset({HAND_OFF_TOOL_NAME})

# Shown to Claude as the tool result of any call voice doesn't make itself.
MAIN_SESSION_HANDOFF_MESSAGE = (
    "Voice only does quick tasks: music, the whiteboard, the brief, sleep mode and "
    f"quick lookups. Hand this to the main Signal session with the {HAND_OFF_TOOL} "
    "tool, called with a one- or two-sentence summary of the job."
)


@dataclass(frozen=True)
class PermissionRequest:
    """One tool call the CLI wants approved.

    Attributes:
        tool_name: The tool, e.g. "Read" or "mcp__audiohub__notify".
        tool_input: The tool's input as Claude sent it.
    """

    tool_name: str
    tool_input: Mapping[str, object]


@dataclass(frozen=True)
class PermissionDecision:
    """The gate's answer to one tool call.

    Attributes:
        is_allowed: True to run the call.
        refusal: Why the call was refused, shown to Claude as the tool result.
            None when allowed.
    """

    is_allowed: bool
    refusal: str | None = None


PermissionDecider = Callable[[PermissionRequest], Awaitable[PermissionDecision]]
"""Takes one request; returns the decision."""


def is_auto_allowed(
    tool_name: str, auto_allow_tools: Collection[str], auto_allow_mcp_servers: Collection[str]
) -> bool:
    """Say whether a tool is on the run-without-asking lists.

    Args:
        tool_name: The tool's name, e.g. "Read" or "mcp__audiohub__notify".
        auto_allow_tools: Exact tool names allowed (from BrainSettings).
        auto_allow_mcp_servers: MCP server names whose tools are allowed.

    Returns:
        True for a listed tool, or a tool of a listed MCP server by its exact name.
    """
    return tool_name in auto_allow_tools or any(
        _is_tool_of_server(tool_name, server) for server in auto_allow_mcp_servers if server
    )


def _is_tool_of_server(tool_name: str, server: str) -> bool:
    """Whether `tool_name` is "mcp__<server>__<snake_case_tool>" for exactly this server."""
    prefix = _MCP_TOOL_PREFIX.format(server=server)
    if not tool_name.startswith(prefix):
        return False
    return _MCP_TOOL_NAME.fullmatch(tool_name[len(prefix) :]) is not None


class PermissionGate:
    """Allows voice's own quick tools and the hand-off; refuses everything else quietly."""

    def __init__(
        self,
        auto_allow_tools: Collection[str],
        project_root: Path,
        *,
        auto_allow_mcp_servers: Collection[str] = (),
    ) -> None:
        """Create the gate.

        Args:
            auto_allow_tools: Exact tool names voice may use.
            project_root: The session's working directory; relative paths start here.
            auto_allow_mcp_servers: MCP servers whose every tool voice may use.
        """
        self._auto_allow_tools = frozenset(auto_allow_tools)
        self._auto_allow_mcp_servers = frozenset(auto_allow_mcp_servers)
        self._project_root = project_root

    async def decide(self, request: PermissionRequest) -> PermissionDecision:
        """Decide one tool call. Matches the PermissionDecider signature.

        Args:
            request: The tool call to decide.

        Returns:
            Allowed, or refused with a message for Claude.
        """
        name, tool_input = request.tool_name, request.tool_input
        paths = self._resolved_targets(request)
        if name in READ_ONLY_TOOLS and targets_secret(name, tool_input, self._project_root):
            logger.info("Refused secret read %s, paths %s", name, paths)
            return PermissionDecision(False, refusal=SECRET_READ_REFUSAL)
        is_allowed = name in ALWAYS_ALLOWED_TOOLS or is_auto_allowed(
            name, self._auto_allow_tools, self._auto_allow_mcp_servers
        )
        if not is_allowed:
            logger.info("Refused %s as a job for the main session", name)
            return PermissionDecision(False, refusal=MAIN_SESSION_HANDOFF_MESSAGE)
        logger.info("Allowed %s, paths %s", name, paths)
        return PermissionDecision(True)

    def _resolved_targets(self, request: PermissionRequest) -> str:
        """The full resolved paths a call targets, joined for the log.

        An untrusted path shows as "None"; a call without paths gives "none".
        """
        paths = target_paths(request.tool_name, request.tool_input)
        return ", ".join(str(resolve_path(path, self._project_root)) for path in paths) or "none"
