"""drive_run: the body of one active run's task, from running to done, failed or cancelled.

It hands over to phases.run_pipeline, which builds the run venv and resumes
after manifest.finished_phases. This task is the only writer of the run's
manifest while it runs (plus synchronous Q&A saves on the same loop thread).
A cancel from /cancel marks the run cancelled; a cancel from daemon shutdown
leaves it running on disk so the next start re-queues it.

A run's end is recorded and announced once: `notify_closed` sets `run.closed`,
and after that neither phases' late unwind nor `record_cancel` writes or
announces it again (a /cancel that timed out has already done both).
"""

import asyncio
import logging
from pathlib import Path

from analysis_chamber.config import ChamberConfig
from analysis_chamber.daemon.backend import Backend
from analysis_chamber.daemon.engine.run_state import (
    RunState,
    fail_run,
    is_shutdown_cancel,
    persist,
)
from analysis_chamber.guard import LeakError
from analysis_chamber.runs import Manifest, Status

logger = logging.getLogger(__name__)

DONE_PERCENT = 100
# Ends a cancel must not overwrite.
ENDED_ON_ITS_OWN = frozenset({Status.DONE, Status.FAILED})


async def drive_run(run: RunState, config: ChamberConfig, backend: Backend) -> None:
    """Run the remaining phases of an approved run and record how it ended.

    Args:
        run: The run (status queued, just taken off the queue).
        config: Chamber config.
        backend: The phase functions and shared objects.

    Raises:
        asyncio.CancelledError: Re-raised; recorded as cancelled only for a /cancel.
    """
    try:
        run.manifest.status = Status.RUNNING
        persist(run, config)
        await _run_phases(run, config, backend)
        if run.manifest.status is Status.RUNNING:
            run.manifest.status = Status.DONE
            run.manifest.percent = DONE_PERCENT
        persist(run, config)
    except asyncio.CancelledError:
        if is_shutdown_cancel(run):
            # Daemon shutdown, not /cancel: persist saved phases' CANCELLED as running,
            # so restore that in memory too. A run that already ended (DONE or FAILED
            # before the cancel landed, e.g. during notifier.done) keeps its status.
            run.manifest.status = Status.RUNNING
        elif run.cancel_requested:
            # phases records a cancel itself; this covers a cancel before it took over.
            await record_cancel(run, config, backend)
        raise
    except Exception as error:
        logger.exception("run %s failed", run.manifest.id)
        fail_run(run, config, f"{type(error).__name__}: {error}")
        await notify_closed(run, backend)


async def _run_phases(run: RunState, config: ChamberConfig, backend: Backend) -> None:
    ctx = backend.make_context(run.run_dir, run.manifest, config)

    async def on_update(manifest: Manifest) -> None:
        run.manifest = manifest  # follow the phase if it swapped the object
        if run.closed or is_shutdown_cancel(run):
            return  # already recorded by /cancel, or a shutdown: no write, no progress
        persist(run, config)
        await backend.notifier.progress(manifest)

    hooks = backend.make_hooks(on_update, _RunNotifier(run, backend))
    await backend.run_pipeline(ctx, backend.agents, hooks)


class _RunNotifier:
    """The notifier phases gets for one run: done passes through, closed goes via notify_closed."""

    def __init__(self, run: RunState, backend: Backend) -> None:
        self._run = run
        self._backend = backend

    async def done(self, manifest: Manifest, top_finding: str, report_path: Path) -> None:
        await self._backend.notifier.done(manifest, top_finding, report_path)

    async def closed(self, manifest: Manifest) -> None:
        await notify_closed(self._run, self._backend)


async def record_cancel(run: RunState, config: ChamberConfig, backend: Backend) -> None:
    """Mark the run cancelled, save it and send its closed notice, unless its end is recorded.

    Args:
        run: The run (cancel_requested set by /cancel).
        config: For the leak guard.
        backend: For the notifier.
    """
    if run.closed or run.manifest.status in ENDED_ON_ITS_OWN:
        return  # recorded already, or it finished before the cancel landed
    run.manifest.status = Status.CANCELLED
    try:
        persist(run, config)
    except (LeakError, ValueError):
        logger.exception("couldn't save the cancelled state of run %s", run.manifest.id)
    await notify_closed(run, backend)


async def notify_closed(run: RunState, backend: Backend) -> None:
    """Send the run's one closed notice; failures are logged only.

    A shutdown cancel gets none (the run resumes next start), and a second call is a no-op.
    """
    if run.closed or is_shutdown_cancel(run):
        return
    run.closed = True
    try:
        await backend.notifier.closed(run.manifest)
    except Exception:
        # A notice is best effort; the run's state is already saved.
        logger.exception("closed notice for run %s failed", run.manifest.id)
