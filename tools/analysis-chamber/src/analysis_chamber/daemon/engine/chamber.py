"""Chamber: the daemon's run registry and the operations behind each HTTP route.

Runs live in memory (seeded at startup by scanning both roots) and on disk in
their manifests. A new run starts under private_root with personal unset and an
opaque id; at approval a non-personal run moves to analyses_root and is renamed to a
readable id (DESIGN.md "Where a run lives"). Every write goes through
run_state.persist, which runs the leak guard.
"""

import asyncio
import logging
from datetime import date
from typing import Any

from analysis_chamber.config import ChamberConfig
from analysis_chamber.daemon.backend import Backend
from analysis_chamber.daemon.engine.pipeline import drive_run, record_cancel
from analysis_chamber.daemon.engine.placement import (
    check_new_run,
    fits_run_dir_limit,
    move_to_analyses,
)
from analysis_chamber.daemon.engine.run_state import (
    TERMINAL_STATUSES,
    ChamberError,
    RunState,
    fail_run,
    persist,
)
from analysis_chamber.daemon.engine.scheduler import Scheduler
from analysis_chamber.daemon.engine.views import brief_view, status_view
from analysis_chamber.guard import LeakError, is_under
from analysis_chamber.runs import (
    Manifest,
    ManifestError,
    Status,
    create_run_dir,
    make_opaque_id,
    make_run_id,
    scan_runs,
    write_manifest,
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
        # Old opaque id -> new readable id, for a run renamed at approval, so a caller
        # still holding the id from /start keeps working until the daemon restarts.
        self._renamed: dict[str, str] = {}
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
        """Create a run under private_root and draft its plan (an agent turn).

        The id is opaque: whether the run is personal isn't known until approval.
        """
        run_id = make_opaque_id(date.today(), self._taken_ids())
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
            run_id = run.manifest.id  # the caller may have sent a pre-rename id
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
            "run_id": manifest.id,  # the readable id, if the run was renamed
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
        """Set the personal flag; a non-personal run is renamed to a readable id and moved
        into analyses_root. A personal run keeps its opaque id."""
        manifest = run.manifest
        manifest.personal = personal
        # Already under analyses_root: a crash after the rename but before persist left it
        # there, so re-approval must not rename it again. A personal answer for it fails at
        # persist's leak guard, as for any personal run outside private_root.
        already_placed = is_under(run.run_dir, self._config.analyses_root)
        if not personal and not already_placed:
            old_id = manifest.id
            new_id = make_run_id(manifest.question, date.today(), self._taken_ids())
            if not fits_run_dir_limit(self._config.analyses_root / new_id):
                new_id = old_id  # the readable name would break the path limit: stay opaque
            manifest.id = new_id  # the leak guard and messages see the new id
            renamed = new_id != old_id
            try:
                # With a new id, the manifest carries it before the folder does. A crash after
                # the rename leaves a matching folder (persist then never ran, so the run is
                # re-approved in place). A crash before it leaves an opaque folder with a slug
                # id; scan_runs resets that to the opaque id, private and unapproved.
                # With no id change nothing needs syncing, and writing personal=False under
                # private_root would let a crash reload it as non-personal there (scan_runs
                # can't spot it, the id matches). So the manifest is written only by persist,
                # after the move.
                if renamed:
                    write_manifest(run.run_dir, manifest)
                run.run_dir = move_to_analyses(run.run_dir, manifest, self._config, new_id)
            except (LeakError, ChamberError, ManifestError):
                manifest.personal, manifest.id = None, old_id  # still private, still unapproved
                if renamed:
                    self._restore_manifest(run)
                raise
            if renamed:
                self._runs[new_id] = self._runs.pop(old_id)
                self._renamed[old_id] = new_id
        run.manifest.status = Status.QUEUED
        persist(run, self._config)

    @staticmethod
    def _restore_manifest(run: RunState) -> None:
        """Put the rolled-back manifest on disk; if even that fails, log it (the caller is
        already raising the real error)."""
        try:
            write_manifest(run.run_dir, run.manifest)
        except ManifestError as error:
            logger.error("couldn't restore run %s's manifest: %s", run.manifest.id, error)

    def _taken_ids(self) -> set[str]:
        # Folder names too: a folder with an unreadable manifest still blocks its id.
        roots = (self._config.analyses_root, self._config.private_root)
        folders = {path.name for root in roots if root.is_dir() for path in root.iterdir()}
        # Renamed runs' old opaque ids too: _get still resolves them, so they can't be reissued.
        return folders | set(self._runs) | set(self._renamed)

    def _get(self, run_id: str) -> RunState:
        run = self._runs.get(self._renamed.get(run_id, run_id))
        if run is None:
            raise ChamberError(f"no run {run_id!r}")
        return run

    @staticmethod
    def _require(run: RunState, status: Status) -> None:
        if run.manifest.status is not status:
            current = run.manifest.status.value
            raise ChamberError(f"run {run.manifest.id} is {current}, not {status.value}")
