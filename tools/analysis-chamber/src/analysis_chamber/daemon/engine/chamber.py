"""Chamber: the daemon's run registry and the operations behind each HTTP route.

Runs live in memory (seeded at startup by scanning both roots) and on disk in
their manifests. A new run starts under private_root with personal unset; at
approval a non-personal run moves to analyses_root (DESIGN.md "Where a run
lives"). Every write goes through run_state.persist, which runs the leak guard.
"""

import asyncio
import logging
from datetime import date
from typing import Any

from analysis_chamber.config import ChamberConfig
from analysis_chamber.daemon.backend import Backend
from analysis_chamber.daemon.engine.pipeline import drive_run, record_cancel
from analysis_chamber.daemon.engine.placement import check_new_run, move_to_analyses
from analysis_chamber.daemon.engine.run_state import (
    TERMINAL_STATUSES,
    ChamberError,
    RunState,
    fail_run,
    persist,
)
from analysis_chamber.daemon.engine.scheduler import Scheduler
from analysis_chamber.daemon.engine.views import brief_view, status_view
from analysis_chamber.guard import LeakError
from analysis_chamber.runs import (
    Manifest,
    Status,
    create_run_dir,
    make_run_id,
    scan_runs,
)

logger = logging.getLogger(__name__)

# How long /cancel waits for an active run to stop before answering.
CANCEL_WAIT_S = 30.0
RESUMABLE = frozenset({Status.RUNNING, Status.QUEUED})
# A /start whose plan draft was cut off (shutdown, crash, dropped request) can never be
# approved, so it's failed with this; the user starts it again.
PLAN_INTERRUPTED = "plan draft interrupted"


class Chamber:
    """Holds every run and carries out start, approve, status, list, ask and cancel."""

    def __init__(self, config: ChamberConfig, backend: Backend) -> None:
        """Args:
        config: Chamber config.
        backend: The phase functions (real or fake).
        """
        self._config = config
        self._backend = backend
        self._runs: dict[str, RunState] = {}
        self._scheduler = Scheduler(config, lambda run: drive_run(run, config, backend))

    def resume(self) -> None:
        """Load runs from both roots; re-queue running and queued ones in created order.

        Runs awaiting approval just wait (spec 21 Q1: plans don't expire), except one
        with no plan, whose draft was cut off: it's failed (PLAN_INTERRUPTED).
        """
        found = scan_runs([self._config.analyses_root, self._config.private_root])
        for run_dir, manifest in found:
            run = self._runs[manifest.id] = RunState(run_dir, manifest)
            if manifest.status is Status.AWAITING_APPROVAL and not manifest.plan_text.strip():
                fail_run(run, self._config, PLAN_INTERRUPTED)
        waiting = [run for run in self._runs.values() if run.manifest.status in RESUMABLE]
        for run in sorted(waiting, key=lambda run: run.manifest.created_at):
            logger.info("resuming run %s after %s", run.manifest.id, run.manifest.finished_phases)
            self._scheduler.enqueue(run)

    async def shutdown(self) -> None:
        """Stop active runs so they resume on the next start."""
        await self._scheduler.shutdown()

    async def start(self, question: str) -> dict[str, Any]:
        """Create a run under private_root and draft its plan (an agent turn)."""
        run_id = make_run_id(question, date.today(), self._taken_ids())
        manifest = Manifest(run_id, question)
        run_dir = check_new_run(manifest, self._config)  # length and leak guard first
        run = RunState(create_run_dir(run_dir.parent, run_id), manifest)
        self._runs[run_id] = run
        async with run.turn_lock:
            persist(run, self._config)
            plan = await self._plan_turn(run, None)
        return {"run_id": run_id, "plan": plan}

    async def approve(
        self, run_id: str, edits: str | None, personal: bool | None
    ) -> dict[str, Any]:
        """Revise the plan (edits given) or approve it and queue the run.

        Raises:
            ChamberError: Unknown run, not awaiting approval, or `personal` unset
                on an approval.
        """
        run = self._get(run_id)
        async with run.turn_lock:
            self._require(run, Status.AWAITING_APPROVAL)
            if not run.manifest.plan_text.strip():
                raise ChamberError(f"run {run_id} has no plan yet")
            if edits and edits.strip():
                plan = await self._plan_turn(run, edits)
                return {"run_id": run_id, "status": run.manifest.status.value, "plan": plan}
            if personal is None:
                raise ChamberError("set personal yes/no to approve the plan")
            self._place(run, personal)
            self._scheduler.enqueue(run)
        manifest = run.manifest
        return {
            "run_id": run_id,
            "status": manifest.status.value,
            "queue_position": manifest.queue_position,
        }

    def status(self, run_id: str) -> dict[str, Any]:
        """The status view of one run."""
        return status_view(self._get(run_id))

    def list_runs(self) -> dict[str, Any]:
        """Every run the daemon knows, oldest first."""
        runs = sorted(self._runs.values(), key=lambda run: run.manifest.created_at)
        return {"runs": [brief_view(run.manifest) for run in runs]}

    async def ask(self, run_id: str, question: str) -> dict[str, Any]:
        """Answer a question about a run with its Q&A agent (an agent turn).

        Asks on one run queue on its turn_lock, so a Q&A session id never has two
        live writers. Mid-run asks fork the lead session (phases' job), so they'd be
        safe in parallel; they queue anyway, which costs only latency.
        """
        run = self._get(run_id)
        backend = self._backend
        async with run.turn_lock:
            ctx = backend.make_context(run.run_dir, run.manifest, self._config)
            answer = await backend.ask(ctx, backend.agents, question)
            persist(run, self._config)  # the Q&A session id may be new
        return {"run_id": run_id, "answer": answer}

    async def cancel(self, run_id: str) -> dict[str, Any]:
        """Cancel an active run, or take a queued or unapproved one out of play.

        Raises:
            ChamberError: Unknown run, or it already ended.
        """
        run = self._get(run_id)
        if run.manifest.status in TERMINAL_STATUSES:
            raise ChamberError(f"run {run_id} already ended ({run.manifest.status.value})")
        run.cancel_requested = True
        if run.task is not None:
            task = run.task
            task.cancel()
            await asyncio.wait([task], timeout=CANCEL_WAIT_S)
            if run.manifest.status not in TERMINAL_STATUSES:
                # Still winding down after the wait (or cancelled before it started): record
                # it now; the late unwind then writes and announces nothing (run.closed).
                await record_cancel(run, self._config, self._backend)
        else:
            self._scheduler.dequeue(run)
            await record_cancel(run, self._config, self._backend)
        return {"run_id": run_id, "status": run.manifest.status.value}

    async def _plan_turn(self, run: RunState, edits: str | None) -> str:
        """Draft (edits None) or revise the plan and save it; a failed or cut-off draft fails it."""
        backend = self._backend
        ctx = backend.make_context(run.run_dir, run.manifest, self._config)
        try:
            if edits is None:
                plan = await backend.draft_plan(ctx, backend.agents)
            else:
                plan = await backend.revise_plan(ctx, backend.agents, edits)
        except (Exception, asyncio.CancelledError) as error:
            # A draft that never finished leaves a plan that can't be approved. A run
            # /cancel ended mid-draft stays cancelled.
            if edits is None and run.manifest.status not in TERMINAL_STATUSES:
                cut_off = isinstance(error, asyncio.CancelledError)
                reason = PLAN_INTERRUPTED if cut_off else f"plan draft failed: {error}"
                fail_run(run, self._config, reason)
            raise
        run.manifest.plan_text = plan
        persist(run, self._config)
        return plan

    def _place(self, run: RunState, personal: bool) -> None:
        """Set the personal flag and move a non-personal run into analyses_root."""
        run.manifest.personal = personal
        if not personal:
            try:
                run.run_dir = move_to_analyses(run.run_dir, run.manifest, self._config)
            except (LeakError, ChamberError):
                run.manifest.personal = None  # still in private_root, still unapproved
                raise
        run.manifest.status = Status.QUEUED
        persist(run, self._config)

    def _taken_ids(self) -> set[str]:
        # Folder names too: a folder with an unreadable manifest still blocks its id.
        roots = (self._config.analyses_root, self._config.private_root)
        folders = {path.name for root in roots if root.is_dir() for path in root.iterdir()}
        return folders | set(self._runs)

    def _get(self, run_id: str) -> RunState:
        run = self._runs.get(run_id)
        if run is None:
            raise ChamberError(f"no run {run_id!r}")
        return run

    @staticmethod
    def _require(run: RunState, status: Status) -> None:
        if run.manifest.status is not status:
            current = run.manifest.status.value
            raise ChamberError(f"run {run.manifest.id} is {current}, not {status.value}")
