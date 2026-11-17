"""Scheduler: the FIFO run queue and the cap on active runs (config.max_parallel_runs).

Approved and resumed runs are enqueued; whenever a slot is free the oldest one
starts as an asyncio task running `drive(run)`. Queued runs keep queue_position
(1 = next) up to date in their manifests. The GPU lock is the gpu package's job.
"""

import asyncio
import logging
from collections import deque
from collections.abc import Callable, Coroutine
from typing import Any

from analysis_chamber.config import ChamberConfig
from analysis_chamber.daemon.engine.run_state import RunState, fail_run, persist
from analysis_chamber.guard import LeakError
from analysis_chamber.runs import Status

logger = logging.getLogger(__name__)

Drive = Callable[[RunState], Coroutine[Any, Any, None]]


class Scheduler:
    """Starts queued runs as slots free up."""

    def __init__(self, config: ChamberConfig, drive: Drive) -> None:
        """Args:
        config: For max_parallel_runs and the leak guard.
        drive: Runs one run to the end (the pipeline task body).
        """
        self._config = config
        self._drive = drive
        self._queue: deque[RunState] = deque()
        self._active: set[RunState] = set()
        self._stopping = False

    def enqueue(self, run: RunState) -> None:
        """Queue a run (status queued) and start it now if a slot is free."""
        run.manifest.status = Status.QUEUED
        self._queue.append(run)
        self._pump()

    def dequeue(self, run: RunState) -> bool:
        """Take a queued run out of the queue. Returns False if it wasn't queued."""
        if run not in self._queue:
            return False
        self._queue.remove(run)
        run.manifest.queue_position = None
        self._renumber()
        return True

    async def shutdown(self) -> None:
        """Cancel active runs without marking them cancelled, so they resume next start."""
        self._stopping = True
        tasks = [run.task for run in self._active if run.task is not None]
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

    def _pump(self) -> None:
        while (
            not self._stopping
            and self._queue
            and len(self._active) < self._config.max_parallel_runs
        ):
            run = self._queue.popleft()
            run.manifest.queue_position = None
            self._active.add(run)
            run.task = asyncio.create_task(self._drive(run), name=f"run-{run.manifest.id}")
            run.task.add_done_callback(lambda _task, run=run: self._finished(run))
        self._renumber()

    def _finished(self, run: RunState) -> None:
        self._active.discard(run)
        run.task = None
        self._pump()

    def _renumber(self) -> None:
        for position, run in enumerate(list(self._queue), start=1):
            run.manifest.queue_position = position
            if not self._save(run):
                # A queued run that can't be saved is failed, not started.
                self._queue.remove(run)
                self._renumber()
                return

    def _save(self, run: RunState) -> bool:
        try:
            persist(run, self._config)
        except LeakError:
            return False  # persist already marked it failed and logged why
        except ValueError as error:
            fail_run(run, self._config, f"can't save the queued run: {error}")
            return False
        return True
