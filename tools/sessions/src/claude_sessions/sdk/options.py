"""build_options: the ClaudeAgentOptions for one managed session.

Managed sessions run in the owner's own repos and should behave like their
normal Claude Code sessions: the claude_code system prompt preset, and user,
project and local settings (CLAUDE.md, permission rules, MCP servers, model
defaults). Four things differ on purpose: every prompt goes to can_use_tool
(the owner's approval dialog), bypassPermissions is refused here and also
disabled through flag settings, so no settings file can switch it on, the
flag settings also deny reads and writes of the owner's secrets
(secret_rules.py), and SIGNAL_BRIEF_SURFACE=managed keeps the brief from
counting it as the owner's.
"""

import json
import logging
from dataclasses import dataclass
from pathlib import Path

from claude_agent_sdk import CanUseTool, ClaudeAgentOptions, SettingSource
from claude_agent_sdk.types import SystemPromptPreset

from claude_sessions.approvals import validate_permission_mode
from claude_sessions.sdk.secret_rules import SECRET_DENY_RULES

logger = logging.getLogger(__name__)

# The options type, re-exported so callers outside this package needn't import the SDK.
SessionOptions = ClaudeAgentOptions

SETTING_SOURCES: tuple[SettingSource, ...] = ("user", "project", "local")

# Without a preset the SDK passes `--system-prompt ""`, which drops Claude Code's
# own system prompt; the preset with no append keeps the CLI's default.
CLAUDE_CODE_PROMPT: SystemPromptPreset = {"type": "preset", "preset": "claude_code"}

# Flag settings outrank every settings file except managed settings:
# - disableBypassPermissionsMode: bypassPermissions stays unavailable even if
#   a repo's settings or a mode switch asks for it.
# - deny: the secret rules. A JSON list carries each rule, spaces and all, as
#   it is; --disallowedTools would pass them comma-joined for the CLI to split.
FLAG_SETTINGS = json.dumps(
    {
        "permissions": {
            "disableBypassPermissionsMode": "disable",
            "deny": list(SECRET_DENY_RULES),
        }
    }
)

# Tells Signal's brief (tools/brief) that the owner isn't watching this session, so its
# prompt hook and brief tools never mark a brief seen. The CLI passes it on to hooks
# and MCP servers.
SESSION_ENV = {"SIGNAL_BRIEF_SURFACE": "managed"}


@dataclass(frozen=True)
class LaunchSpec:
    """What to launch: where, with which model and mode, and as which Claude session.

    Exactly one of session_id (a new session with that id) and resume (an
    existing session id) is set.

    Attributes:
        cwd: The repo folder Claude Code runs in.
        model: Model name or alias ("sonnet"), or None for the settings' default.
        permission_mode: "default", "acceptEdits" or "plan".
        session_id: For a new session, the UUID to store it under.
        resume: For a resumed session, the existing Claude session id.
    """

    cwd: Path
    model: str | None
    permission_mode: str
    session_id: str | None = None
    resume: str | None = None


def build_options(spec: LaunchSpec, can_use_tool: CanUseTool) -> ClaudeAgentOptions:
    """Assemble the options for one session's ClaudeSDKClient.

    Args:
        spec: Where and how to launch.
        can_use_tool: Decides tool calls the CLI would prompt for.

    Returns:
        Options for ClaudeSDKClient.

    Raises:
        PermissionModeError: spec.permission_mode isn't allowed (bypassPermissions never is).
        ValueError: Both or neither of session_id and resume are set.
    """
    mode = validate_permission_mode(spec.permission_mode)
    if (spec.session_id is None) == (spec.resume is None):
        raise ValueError("set exactly one of session_id (new session) and resume")
    return ClaudeAgentOptions(
        cwd=str(spec.cwd),
        model=spec.model or None,
        system_prompt=CLAUDE_CODE_PROMPT,
        setting_sources=list(SETTING_SOURCES),
        settings=FLAG_SETTINGS,
        permission_mode=mode,
        can_use_tool=can_use_tool,
        session_id=spec.session_id,
        resume=spec.resume,
        env=dict(SESSION_ENV),
        stderr=_log_cli_stderr,
    )


def _log_cli_stderr(line: str) -> None:
    """Forward the CLI's stderr to the daemon log; it only writes there when something's wrong."""
    logger.warning("claude cli: %s", line.rstrip())
