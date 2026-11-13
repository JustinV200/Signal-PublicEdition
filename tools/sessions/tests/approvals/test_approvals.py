"""Tests for the permission-mode policy and DialogApprover (with a fake dialog)."""

import asyncio

import pytest

from claude_sessions.approvals import (
    ApprovalRequest,
    DialogApprover,
    PermissionModeError,
    validate_permission_mode,
)

REQUEST = ApprovalRequest("s-1", "OtherRepo", "Bash", "Claude wants to run a command\ngit push")


@pytest.mark.parametrize("mode", ["bypassPermissions", "dontAsk", "auto", "", None])
def test_only_prompting_modes_are_allowed(mode: object) -> None:
    with pytest.raises(PermissionModeError):
        validate_permission_mode(mode)
    for allowed in ("default", "acceptEdits", "plan"):
        assert validate_permission_mode(allowed) == allowed


@pytest.mark.asyncio
async def test_dialog_shows_repo_and_tool_and_returns_the_answer() -> None:
    shown: list[tuple[str, str, float]] = []

    async def show(title: str, text: str, *, timeout_s: float) -> bool:
        shown.append((title, text, timeout_s))
        return True

    approver = DialogApprover(timeout_s=120, show_dialog=show)

    assert await approver.approve(REQUEST) is True
    [(title, text, timeout_s)] = shown
    assert "OtherRepo" in title and "git push" in text and timeout_s == 120


@pytest.mark.asyncio
async def test_a_dialog_that_fails_to_show_denies() -> None:
    async def broken(title: str, text: str, *, timeout_s: float) -> bool:
        raise OSError("no desktop")

    assert await DialogApprover(show_dialog=broken).approve(REQUEST) is False


@pytest.mark.asyncio
async def test_the_timeout_counts_time_queued_behind_another_dialog() -> None:
    shown: list[float] = []

    async def owner_away(title: str, text: str, *, timeout_s: float) -> bool:
        shown.append(timeout_s)
        await asyncio.sleep(timeout_s)  # The dialog times out by itself.
        return False

    notes: list[str] = []
    first = ApprovalRequest("s-1", "OtherRepo", "Bash", "a", on_shown=lambda: notes.append("a"))
    queued = ApprovalRequest("s-1", "OtherRepo", "Bash", "b", on_shown=lambda: notes.append("b"))
    approver = DialogApprover(timeout_s=1.2, show_dialog=owner_away)

    answers = await asyncio.gather(approver.approve(first), approver.approve(queued))

    # The queued call ran out of time behind the first, so no second dialog (or note).
    assert answers == [False, False] and len(shown) == 1 and notes == ["a"]
