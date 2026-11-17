"""run_pipeline: collect, analyse, critique and report for an approved run, with checkpoints.

Each phase sets phase/percent/timings and awaits on_update (the daemon persists),
runs, then is appended to finished_phases and checkpointed the same way. A rerun
after a crash skips finished phases; a phase that was started but never finished
gets an "interrupted" note so the lead checks the folder before continuing.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from analysis_chamber.phases.critique import run_critique
from analysis_chamber.phases.deps import PhaseAgents, PhaseError, PipelineHooks, StepCall
from analysis_chamber.phases.report import (
    NO_TOP_FINDING,
    ReportResult,
    existing_outputs,
    run_report,
)
from analysis_chamber.phases.steps import run_analyse, run_collect
from analysis_chamber.runs import PHASE_ORDER, Phase, Status, utc_now_iso

if TYPE_CHECKING:
    from analysis_chamber.agents import RunContext

log = logging.getLogger(__name__)

STEPS = {
    Phase.COLLECT: run_collect,
    Phase.ANALYSE: run_analyse,
    Phase.CRITIQUE: run_critique,
    Phase.REPORT: run_report,
}
# Coarse percent band (start, end) per phase; percent is 100 only when done.
PERCENT_BANDS = {
    Phase.COLLECT: (5, 30),
    Phase.ANALYSE: (30, 65),
    Phase.CRITIQUE: (65, 85),
    Phase.REPORT: (85, 99),
}
# Phases after which the run venv may hold new installs.
INSTALL_PHASES = {Phase.ANALYSE, Phase.REPORT}
DONE_PERCENT = 100


def remaining_phases(finished: list[str]) -> list[Phase]:
    """The pipeline phases (everything after plan) not yet in finished, in order."""
    return [phase for phase in PHASE_ORDER if phase in STEPS and phase.value not in finished]


async def run_pipeline(ctx: RunContext, agents: PhaseAgents, hooks: PipelineHooks) -> None:
    """Run the remaining phases of an approved run, then notify done.

    Failure is handled here, not raised: status failed, last_error set, partial
    outputs kept, notifier.closed awaited. Cancellation sets status cancelled,
    awaits notifier.closed and re-raises CancelledError.

    Raises:
        asyncio.CancelledError: The run was cancelled.
    """
    manifest = ctx.manifest
    if Phase.PLAN.value not in manifest.finished_phases:
        manifest.finished_phases.insert(0, Phase.PLAN.value)  # approval ends the plan phase
    was_done = manifest.status is Status.DONE
    manifest.status, manifest.last_error = Status.RUNNING, None
    try:
        # Idempotent, so always called; blocking (uv), so off the event loop.
        await asyncio.to_thread(hooks.kit.make_run_venv, ctx.run_dir, ctx.config)
        result = None
        for phase in remaining_phases(manifest.finished_phases):
            result = await _run_phase(ctx, agents, hooks, phase)
        result = result or _saved_report(ctx)
    except asyncio.CancelledError:
        await _close(ctx, hooks, Status.CANCELLED, None)
        raise
    except Exception as error:
        log.exception("run %s failed in %s", manifest.id, manifest.phase)
        await _close(ctx, hooks, Status.FAILED, f"{manifest.phase.value}: {error}")
        return
    await _finish(ctx, hooks, result, was_done)


async def _run_phase(
    ctx: RunContext, agents: PhaseAgents, hooks: PipelineHooks, phase: Phase
) -> ReportResult | None:
    """Run one phase between its start and finish checkpoints; returns its step result."""
    manifest = ctx.manifest
    start, end = PERCENT_BANDS[phase]
    timing = manifest.timings.setdefault(phase.value, {})
    # A start time with no finish means a crash or restart cut this phase off.
    interrupted = "started" in timing and "finished" not in timing
    if not interrupted:
        # A resumed phase keeps its first start, so the timing spans the whole phase.
        timing["started"] = utc_now_iso()
    manifest.phase, manifest.percent = phase, start
    await hooks.on_update(manifest)

    async def progress(fraction: float) -> None:
        manifest.percent = start + round((end - start) * min(max(fraction, 0.0), 1.0))
        await hooks.on_update(manifest)

    intro = (
        f"The {phase.value} phase was interrupted. Check the run folder state, "
        "then redo or finish it.\n\n"
        if interrupted
        else ""
    )
    result = await STEPS[phase](ctx, agents, StepCall(intro, progress))
    if phase in INSTALL_PHASES:
        manifest.installs = await asyncio.to_thread(
            hooks.kit.list_installs, ctx.run_dir, ctx.config
        )
    timing["finished"] = utc_now_iso()
    manifest.finished_phases.append(phase.value)
    manifest.percent = end
    await hooks.on_update(manifest)
    return result


def _saved_report(ctx: RunContext) -> ReportResult:
    """The report from an earlier attempt, when the report phase was already finished.

    Raises:
        PhaseError: No report path was recorded.
    """
    report_file = ctx.manifest.outputs.get("report")
    if not report_file:
        raise PhaseError("the report phase finished but no report was recorded")
    return ReportResult(ctx.run_dir / report_file, NO_TOP_FINDING)


async def _finish(
    ctx: RunContext, hooks: PipelineHooks, result: ReportResult, was_done: bool
) -> None:
    """Mark the run done and send the done notification.

    If the report checkpoint was saved but the crash came before status done, the
    ping was never sent, so it's sent now (with the saved report path). A run that
    was already done isn't pinged twice.
    """
    manifest = ctx.manifest
    manifest.status, manifest.percent = Status.DONE, DONE_PERCENT
    await hooks.on_update(manifest)
    if not was_done:
        await hooks.notifier.done(manifest, result.top_finding, result.report_path)


async def _close(ctx: RunContext, hooks: PipelineHooks, status: Status, error: str | None) -> None:
    """Record a failed or cancelled run, keeping whatever outputs exist."""
    manifest = ctx.manifest
    manifest.status = status
    if error is not None:
        manifest.last_error = error
    manifest.outputs = existing_outputs(ctx.run_dir, manifest.report_format)
    await hooks.on_update(manifest)
    await hooks.notifier.closed(manifest)
