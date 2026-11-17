"""build_hooks: the `hooks=` value for every chamber agent's ClaudeAgentOptions.

All PreToolUse. send_block_hook runs on every tool; shell_send_hook, page_fetch_hook,
env_file_hook and (for runs not marked non-personal) personal_write_hook run on shell
commands and file writes; for the lead and qa roles, raw_read_hook keeps file and shell
reads out of data/raw/signal/. Any deny wins. Every hook is wrapped in fail_closed, so
a crash denies. The agents package adds its own matchers (e.g. the PostToolUse
free-text swap) through `extra`.
"""

from functools import partial
from typing import TYPE_CHECKING

from claude_agent_sdk import HookMatcher

from analysis_chamber.security.common import SHELL_AND_WRITE_MATCHER, SecurityHook, fail_closed
from analysis_chamber.security.env_file import env_file_hook
from analysis_chamber.security.head_check import ContentTypeChecker, head_content_type
from analysis_chamber.security.page_fetch import page_fetch_hook
from analysis_chamber.security.personal_write import personal_write_hook
from analysis_chamber.security.raw_read import RAW_READ_MATCHER, raw_read_hook
from analysis_chamber.security.send_block import allowed_mcp_tools, send_block_hook
from analysis_chamber.security.shell_send import shell_send_hook

if TYPE_CHECKING:  # type only: agents imports this package, so no runtime import back
    from analysis_chamber.agents.context import RunContext

PRE_TOOL_USE = "PreToolUse"
# Roles that see only extracts of Signal free text (the critic and signup never get it).
RAW_SIGNAL_BLOCKED_ROLES = frozenset({"lead", "qa"})
# Per-matcher hook timeout (the SDK default is 60 s). A timed-out hook may let the call
# through, so keep it well above rules.fetch_rules.HEAD_DEADLINE_S (12 s), the longest
# any hook here takes.
SECURITY_HOOK_TIMEOUT_S = 30.0


def _matcher(matcher: str | None, hooks: list[SecurityHook]) -> HookMatcher:
    """A HookMatcher whose hooks fail closed, with the security timeout."""
    guarded = [fail_closed(hook) for hook in hooks]
    return HookMatcher(matcher=matcher, hooks=guarded, timeout=SECURITY_HOOK_TIMEOUT_S)


def build_hooks(
    ctx: "RunContext",
    role: str = "lead",
    *,
    extra: dict[str, list[HookMatcher]] | None = None,
    content_type_checker: ContentTypeChecker = head_content_type,
) -> dict[str, list[HookMatcher]]:
    """Build the security hooks for one chamber agent session.

    Args:
        ctx: The run; its manifest's personal flag decides the write hook.
        role: "lead", "critic", "qa" or "signup" (picks the MCP allowlist).
        extra: More matchers per hook event (e.g. {"PostToolUse": [...]}), appended
            after the security ones.
        content_type_checker: The page-fetch hook's Content-Type lookup (fake in tests).

    Returns:
        {event: [HookMatcher, ...]} for ClaudeAgentOptions(hooks=...).

    Raises:
        ValueError: on an unknown role.
    """
    allowed_mcp_tools(role)  # fail fast on a bad role, not on the first tool call
    content_hooks: list[SecurityHook] = [
        partial(shell_send_hook, ctx=ctx),
        partial(page_fetch_hook, checker=content_type_checker),
        partial(env_file_hook, ctx=ctx),
    ]
    if ctx.manifest.personal is not False:
        content_hooks.append(partial(personal_write_hook, ctx=ctx))
    pre_tool_use = [
        _matcher(
            None,
            [partial(send_block_hook, role=role, signup_account=ctx.config.signup_mail_account)],
        ),
        _matcher(SHELL_AND_WRITE_MATCHER, content_hooks),
    ]
    if role in RAW_SIGNAL_BLOCKED_ROLES:
        pre_tool_use.append(_matcher(RAW_READ_MATCHER, [partial(raw_read_hook, ctx=ctx)]))
    hooks: dict[str, list[HookMatcher]] = {PRE_TOOL_USE: pre_tool_use}
    for event, matchers in (extra or {}).items():
        hooks.setdefault(event, []).extend(matchers)
    return hooks
