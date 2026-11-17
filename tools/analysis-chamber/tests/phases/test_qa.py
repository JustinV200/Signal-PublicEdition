"""ask: mid-run answers fork the lead and are flagged partial; done runs keep one Q&A session."""

import pytest
from support.phases_fakes import make_ctx, ok, wire

from analysis_chamber.phases import ask
from analysis_chamber.runs import Phase, Status


def lead_session(ctx):
    ctx.manifest.sessions.update(lead="lead-1", lead_cwd=str(ctx.run_dir))


@pytest.mark.asyncio
async def test_mid_run_ask_forks_lead_flags_partial_and_logs(tmp_path):
    ctx = make_ctx(tmp_path, status=Status.RUNNING, phase=Phase.ANALYSE)
    lead_session(ctx)
    agents, _hooks, runner, _ = wire(ctx, lambda call, run_dir: ok("about 4%", "fork-1"))

    answer = await ask(ctx, agents, "What if we drop 2020?")

    assert runner.calls[0].options == ("qa", "lead-1", True)
    assert runner.calls[0].resume == "lead-1"
    assert answer.startswith("Based on partial results") and "about 4%" in answer
    assert "qa" not in ctx.manifest.sessions
    qa_log = (ctx.run_dir / "qa.md").read_text(encoding="utf-8")
    assert "What if we drop 2020?" in qa_log and "about 4%" in qa_log


@pytest.mark.asyncio
async def test_done_ask_forks_once_then_resumes_qa_session(tmp_path):
    ctx = make_ctx(tmp_path, status=Status.DONE, phase=Phase.REPORT)
    lead_session(ctx)
    agents, _hooks, runner, _ = wire(ctx, lambda call, run_dir: ok("answer", "qa-1"))

    await ask(ctx, agents, "first?")
    await ask(ctx, agents, "second?")

    assert runner.calls[0].options == ("qa", "lead-1", True)
    assert runner.calls[1].options == ("qa", "qa-1", False)
    assert runner.calls[1].resume == "qa-1" and runner.calls[1].prompt == "second?"
    assert ctx.manifest.sessions["qa"] == "qa-1"
    assert (ctx.run_dir / "qa.md").read_text(encoding="utf-8").count("**Q:**") == 2
