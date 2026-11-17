"""RunState: one run as the daemon holds it, and the only way the daemon writes its manifest.

Every manifest write goes through `persist`, which runs the leak guard first, so
the daemon never writes into a folder the run's personal flag forbids. Writes are
plain synchronous calls on the daemon's single event-loop thread, so two writes to
one run can never interleave (write_manifest's temp name is per process); that is
the "one writer per run" rule from DESIGN.md without needing a lock.

`persist` is also the one guard that keeps a daemon shutdown from saving the
CANCELLED that phases records on any cancel: whoever writes during that unwind
(the pipeline, a mid-run ask), the disk keeps "running" so the run resumes.
"""

import asyncio
import logging
from dataclasses import dataclass, field, replace
from pathlib import Path

from analysis_chamber.config import ChamberConfig
from analysis_chamber.guard import LeakError, check_run_location
from analysis_chamber.runs import Manifest, Status, write_manifest

logger = logging.getLogger(__name__)

TERMINAL_STATUSES = frozenset({Status.DONE, Status.FAILED, Status.CANCELLED})


class ChamberError(Exception):
    """A request the daemon refuses (unknown run, wrong state, bad field). Sent to the caller."""


@dataclass(eq=False)  # identity equality: runs go in sets and the queue
class RunState:
    """A run's folder and live manifest.

    Attributes:
        run_dir: The run folder (moves to analyses_root at approval when not personal).
        manifest: The live manifest; phases mutate this same object.
        turn_lock: Held while an agent turn (plan, revise, ask) runs, one at a time per run.
        task: The pipeline task while the run is active.
        cancel_requested: Set by /cancel, so a shutdown cancel isn't mistaken for one.
        closed: Its end (failed or cancelled) was announced; nothing announces or records it again.
    """

    run_dir: Path
    manifest: Manifest
    turn_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    task: asyncio.Task[None] | None = None
    cancel_requested: bool = False
    closed: bool = False


def is_shutdown_cancel(run: RunState) -> bool:
    """True while an active run unwinds from a shutdown: CANCELLED that no /cancel asked for.

    The task must really be cancelling, so a CancelledError raised inside the pipeline
    without a cancel (an SDK quirk, say) is recorded as cancelled, not resumed.
    """
    return (
        run.task is not None
        and run.task.cancelling() > 0
        and run.manifest.status is Status.CANCELLED
        and not run.cancel_requested
    )


def persist(run: RunState, config: ChamberConfig) -> None:
    """Write the run's manifest after checking its folder is allowed.

    Args:
        run: The run; its manifest's updated_at is refreshed from the written copy.
            A shutdown cancel (is_shutdown_cancel) is written as running.
        config: For the leak guard's roots.

    Raises:
        LeakError: The folder breaks the personal rule. The run is marked failed
            in memory and nothing is written.
        ManifestError: The write failed.
    """
    try:
        check_run_location(run.manifest, run.run_dir, config)
    except LeakError as error:
        _mark_failed(run.manifest, f"leak guard: {error}")
        logger.error("refused to write run %s at %s: %s", run.manifest.id, run.run_dir, error)
        raise
    manifest = run.manifest
    if is_shutdown_cancel(run):
        manifest = replace(manifest, status=Status.RUNNING)  # resumes on the next start
    run.manifest.updated_at = write_manifest(run.run_dir, manifest).updated_at


def fail_run(run: RunState, config: ChamberConfig, message: str) -> None:
    """Mark the run failed with `message` and save it if the leak guard allows.

    Args:
        run: The run.
        config: For the leak guard.
        message: Goes in last_error (and the status view).
    """
    _mark_failed(run.manifest, message)
    try:
        persist(run, config)
    except (LeakError, ValueError):
        # Already logged by persist (leak) or a broken disk; the in-memory state still shows it.
        logger.exception("couldn't save failed state of run %s", run.manifest.id)


def _mark_failed(manifest: Manifest, message: str) -> None:
    manifest.status = Status.FAILED
    manifest.last_error = message
    manifest.queue_position = None
