"""Plan drafting collects nothing, and lead sessions resume only when it's safe (spike rules)."""

import pytest
from support.phases_fakes import failed, make_ctx, ok, wire

from analysis_chamber.phases import draft_plan, revise_plan


@pytest.mark.asyncio
async def test_draft_plan_is_one_planning_turn_and_adds_personal_section(tmp_path):
    ctx = make_ctx(tmp_path)
    agents, _hooks, runner, _ = wire(ctx, lambda call, run_dir: ok("## Question\nQ", "lead-1"))

    plan = await draft_plan(ctx, agents)

    assert len(runner.calls) == 1
    call = runner.calls[0]
    assert call.resume is None and call.options == ("plan",)
    assert "planning only" in call.prompt and "What moves X?" in call.prompt
    assert (ctx.run_dir / "plan.md").read_text(encoding="utf-8") == plan == ctx.manifest.plan_text
    assert "The user must choose" in plan
    assert str(ctx.config.private_root / ctx.manifest.id) in plan
    assert str(ctx.config.analyses_root / ctx.manifest.id) in plan
    assert ctx.manifest.sessions["lead"] == "lead-1"


# (stored cwd is the run folder?, resume outcome) -> expect a resume attempt?, fresh call seeded?
@pytest.mark.parametrize(
    ("same_cwd", "resume_outcome", "expect_resume", "expect_fresh"),
    [
        (True, "ok", True, False),  # normal resume
        (True, "error", True, True),  # resume returns an error: fresh session seeded from disk
        (True, "raise", True, True),  # regression: a refused resume raises from the SDK
        (False, "ok", False, True),  # run moved at approval: never resume the old session
    ],
)
@pytest.mark.asyncio
async def test_revise_plan_resume_rules(
    tmp_path, same_cwd, resume_outcome, expect_resume, expect_fresh
):
    ctx = make_ctx(tmp_path, plan_text="old plan")
    cwd = str(ctx.run_dir) if same_cwd else str(tmp_path / "private" / "elsewhere")
    ctx.manifest.sessions.update(lead="old", lead_cwd=cwd)

    def reply(call, run_dir):
        if call.resume and resume_outcome == "raise":
            raise RuntimeError("ProcessError: session not found")
        if call.resume:
            return ok("revised", "old") if resume_outcome == "ok" else failed()
        return ok("revised", "new")

    agents, _hooks, runner, _ = wire(ctx, reply)
    await revise_plan(ctx, agents, "drop 2020")

    assert all(call.options == ("plan",) for call in runner.calls)
    assert any(call.resume == "old" for call in runner.calls) == expect_resume
    fresh = [call for call in runner.calls if call.resume is None]
    assert bool(fresh) == expect_fresh
    if expect_fresh:
        assert "new session" in fresh[0].prompt and "old plan" in fresh[0].prompt
        assert ctx.manifest.sessions == {"lead": "new", "lead_cwd": str(ctx.run_dir)}
    assert "drop 2020" in runner.calls[-1].prompt
