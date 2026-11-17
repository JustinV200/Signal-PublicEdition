"""run_pipeline: resume order, critique loop, report-format leak rule, failure and cancel."""

import asyncio

import pytest
from support.phases_fakes import failed, make_ctx, ok, wire

from analysis_chamber.phases import run_pipeline
from analysis_chamber.runs import Status


def scripted(critic_replies, report_format="md", lead_error_in=None):
    """A runner reply: critics answer from critic_replies; the lead writes files as asked."""
    critic_iter = iter(critic_replies)

    def reply(call, run_dir):
        if call.options == ("critic",):
            return ok(next(critic_iter), "critic")
        if lead_error_in and lead_error_in in call.prompt:
            return failed()
        if "Collect phase" in call.prompt:
            (run_dir / "sources.json").write_text('[{"name": "FRED", "url": "u"}]', "utf-8")
        if "Report phase" in call.prompt:
            name = "report.md" if report_format == "md" else "report.html"
            (run_dir / name).write_text("r", "utf-8")
            (run_dir / "writeup.md").write_text("w", "utf-8")
            return ok(f"done\nREPORT_FORMAT: {report_format}\nTOP_FINDING: X rose 4%", "lead")
        return ok("| 1 | f | Major | Fixed: x |", "lead")

    return reply


@pytest.mark.asyncio
async def test_resume_skips_finished_and_flags_interrupted_phase(tmp_path):
    ctx = make_ctx(
        tmp_path,
        finished_phases=["plan", "collect"],
        timings={"analyse": {"started": "2026-11-16T00:00:00+00:00"}},
    )
    agents, hooks, runner, notifier = wire(ctx, scripted(["NO_FINDINGS"]))

    await run_pipeline(ctx, agents, hooks)

    prompts = [call.prompt for call in runner.calls]
    assert not any("Collect phase" in prompt for prompt in prompts)
    assert "The analyse phase was interrupted" in prompts[0]
    assert ctx.manifest.finished_phases == ["plan", "collect", "analyse", "critique", "report"]
    assert ctx.manifest.status is Status.DONE and ctx.manifest.percent == 100
    assert ctx.manifest.installs == [{"package": "ruptures", "version": "1.1.9"}]
    assert notifier.done_calls == [("X rose 4%", ctx.run_dir / "report.md")]
    # Live run 1: a resume overwrote the analyse start with the restart time.
    assert ctx.manifest.timings["analyse"]["started"] == "2026-11-16T00:00:00+00:00"


@pytest.mark.parametrize(
    ("critic_replies", "rounds"),
    [(["1. leak", "2. still leaky"], 2), (["NO_FINDINGS"], 1)],
)
@pytest.mark.asyncio
async def test_critique_rounds_use_fresh_critics_and_are_recorded(tmp_path, critic_replies, rounds):
    ctx = make_ctx(tmp_path, finished_phases=["plan", "collect", "analyse"])
    agents, hooks, runner, _ = wire(ctx, scripted(critic_replies))

    await run_pipeline(ctx, agents, hooks)

    critic_calls = [call for call in runner.calls if call.options == ("critic",)]
    assert len(critic_calls) == rounds <= ctx.config.critic_rounds_max
    assert all(call.resume is None for call in critic_calls)
    critique = (ctx.run_dir / "critique.md").read_text(encoding="utf-8")
    assert critique.count("## Round") == rounds
    if critic_replies[0] != "NO_FINDINGS":
        assert "1. leak" in critique and "Fixed: x" in critique


@pytest.mark.parametrize(
    ("start", "outputs", "end", "dones", "closed"),
    [
        (Status.RUNNING, {"report": "report.md"}, Status.DONE, 1, 0),  # lost ping is resent
        (Status.DONE, {"report": "report.md"}, Status.DONE, 0, 0),  # never pinged twice
        (Status.RUNNING, {}, Status.FAILED, 0, 1),  # no report recorded: fail, no ping
    ],
)
@pytest.mark.asyncio
async def test_rerun_after_report_checkpoint(tmp_path, start, outputs, end, dones, closed):
    # Regression: a crash between the report checkpoint and status done lost the ping.
    ctx = make_ctx(
        tmp_path,
        status=start,
        finished_phases=["plan", "collect", "analyse", "critique", "report"],
        outputs=outputs,
    )
    agents, hooks, runner, notifier = wire(ctx, scripted([]))

    await run_pipeline(ctx, agents, hooks)

    assert runner.calls == [] and ctx.manifest.status is end
    assert len(notifier.done_calls) == dones and notifier.closed_calls == closed
    if dones:
        assert notifier.done_calls == [("see the writeup", ctx.run_dir / "report.md")]


# Only personal=False may keep the artifact format (spec 7.5).
@pytest.mark.parametrize(
    ("personal", "recorded"), [(True, "html"), (None, "html"), (False, "artifact")]
)
@pytest.mark.asyncio
async def test_artifact_format_only_for_non_personal_runs(tmp_path, personal, recorded):
    ctx = make_ctx(
        tmp_path, personal=personal, finished_phases=["plan", "collect", "analyse", "critique"]
    )
    agents, hooks, runner, _ = wire(ctx, scripted([], report_format="artifact"))

    await run_pipeline(ctx, agents, hooks)

    assert ctx.manifest.report_format == recorded
    assert ("ipynb or artifact" in runner.calls[0].prompt) == (personal is False)


@pytest.mark.asyncio
async def test_failure_keeps_partial_outputs_and_closes_without_done(tmp_path):
    ctx = make_ctx(tmp_path, finished_phases=["plan"])
    agents, hooks, _runner, notifier = wire(ctx, scripted([], lead_error_in="Analysis phase"))

    await run_pipeline(ctx, agents, hooks)

    assert ctx.manifest.status is Status.FAILED
    assert ctx.manifest.last_error.startswith("analyse:")
    assert ctx.manifest.finished_phases == ["plan", "collect"]
    assert ctx.manifest.outputs == {"sources": "sources.json"}
    assert notifier.closed_calls == 1 and notifier.done_calls == []


@pytest.mark.asyncio
async def test_cancel_sets_cancelled_closes_and_reraises(tmp_path):
    ctx = make_ctx(tmp_path, finished_phases=["plan"])

    def reply(call, run_dir):
        raise asyncio.CancelledError

    agents, hooks, _runner, notifier = wire(ctx, reply)
    with pytest.raises(asyncio.CancelledError):
        await run_pipeline(ctx, agents, hooks)

    assert ctx.manifest.status is Status.CANCELLED
    assert notifier.closed_calls == 1 and notifier.done_calls == []


# Regression: collect used to replace manifest.sources, dropping tool-recorded ones.
# A repeated url updates the tool record's note (and blank name) instead of duplicating.
@pytest.mark.parametrize(
    ("file_text", "expected_urls", "expected_u1"),
    [
        (
            '﻿[{"name": "mail", "url": "mail:q"}, {"name": "FRED", "url": "u1", "note": "A"}]',
            ["u1", "mail:q"],
            {"name": "FRED", "note": "A"},
        ),
        ('[{"name": "dup", "url": "u1", "note": ""}]', ["u1"], {"name": "dup", "note": "fetch"}),
        ("not json {", ["u1"], {"name": "", "note": "fetch"}),
    ],
)
@pytest.mark.asyncio
async def test_collect_merges_sources_json_into_tool_recorded_sources(
    tmp_path, file_text, expected_urls, expected_u1
):
    ctx = make_ctx(tmp_path, finished_phases=["plan"])
    ctx.manifest.sources.append({"name": "", "url": "u1", "status": "ok", "note": "fetch"})

    def reply(call, run_dir):
        if "Collect phase" in call.prompt:
            (run_dir / "sources.json").write_text(file_text, encoding="utf-8")
            return ok()
        return failed()  # stop the run after collect

    agents, hooks, _runner, _ = wire(ctx, reply)
    await run_pipeline(ctx, agents, hooks)
    assert [source["url"] for source in ctx.manifest.sources] == expected_urls
    first = ctx.manifest.sources[0]
    assert {"name": first["name"], "note": first["note"]} == expected_u1
