"""Tests for build_hooks: which hooks a session gets, and the merge point for extras."""

import pytest
from claude_agent_sdk import HookMatcher
from support.security_hooks import hook_input, is_deny

from analysis_chamber.security import build_hooks
from analysis_chamber.security.rules.fetch_rules import HEAD_DEADLINE_S


async def _decide(hooks: dict, tool: str, **tool_input: object) -> bool:
    """Run every PreToolUse hook whose matcher covers the tool; True if any denies."""
    for matcher in hooks["PreToolUse"]:
        if matcher.matcher is None or tool in matcher.matcher.split("|"):
            for hook in matcher.hooks:
                if is_deny(await hook(hook_input(tool, **tool_input), "u", {})):
                    return True
    return False


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("personal", "repo_write_denied"), [(None, True), (True, True), (False, False)]
)
async def test_write_hook_only_for_runs_not_marked_non_personal(
    make_ctx, personal, repo_write_denied
) -> None:
    hooks = build_hooks(make_ctx(personal), "lead", content_type_checker=lambda url: None)
    repo_write = {"file_path": r"C:\work\Signal\life\a.md", "content": "x"}
    assert await _decide(hooks, "Write", **repo_write) is repo_write_denied
    assert await _decide(hooks, "mcp__mail__mail_send_draft")
    assert await _decide(hooks, "PowerShell", command="iwr https://example.org/blog")
    assert await _decide(hooks, "PowerShell", command="gmcli send")
    assert not await _decide(hooks, "PowerShell", command="python code/a.py")


def test_extra_matchers_appended_and_unknown_role_rejected(make_ctx) -> None:
    post = HookMatcher(matcher="mcp__mail__mail_read", hooks=[])
    pre = HookMatcher(matcher="Read", hooks=[])
    hooks = build_hooks(make_ctx(False), "lead", extra={"PostToolUse": [post], "PreToolUse": [pre]})
    assert hooks["PostToolUse"] == [post]
    assert hooks["PreToolUse"][-1] is pre and len(hooks["PreToolUse"]) == 4
    with pytest.raises(ValueError):
        build_hooks(make_ctx(False), "writer")


@pytest.mark.asyncio
async def test_hooks_fail_closed(make_ctx) -> None:
    ctx = make_ctx(False)
    unreadable = ctx.run_dir / "code" / "folder.py"  # a folder: reading it as a script raises
    unreadable.mkdir()
    hooks = build_hooks(ctx, "lead")
    edit = {"file_path": str(unreadable), "old_string": "a", "new_string": "b"}
    assert await _decide(hooks, "Edit", **edit)
    assert all(m.timeout and m.timeout > HEAD_DEADLINE_S for m in hooks["PreToolUse"])


@pytest.mark.asyncio
@pytest.mark.parametrize(("role", "denied"), [("lead", True), ("qa", True), ("critic", False)])
async def test_raw_signal_reads_blocked_for_lead_and_qa(make_ctx, role: str, denied: bool) -> None:
    hooks = build_hooks(make_ctx(False), role)
    assert await _decide(hooks, "Read", file_path="data/raw/signal/mail.json") is denied
