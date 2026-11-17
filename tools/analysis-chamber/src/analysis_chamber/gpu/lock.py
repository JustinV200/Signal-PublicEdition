"""Cross-process exclusive GPU lock (msvcrt byte lock on state_dir/gpu.lock).

Part of analysis_chamber.gpu. The OS drops the lock if the holder dies.
"""

from __future__ import annotations

import msvcrt
import subprocess
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from analysis_chamber.gpu.job_object import KillOnCloseJob

LOCK_FILE_NAME = "gpu.lock"
POLL_INTERVAL_S = 0.2  # how often a waiter retries the lock


class GpuLockTimeout(TimeoutError):
    """The GPU lock was not acquired before the timeout."""


@contextmanager
def gpu_lock(state_dir: Path, timeout_s: float | None = None) -> Iterator[None]:
    """Hold the exclusive GPU lock for the with-block.

    Blocks (polling) until held. Raises GpuLockTimeout after timeout_s seconds
    (None waits forever). Released on exit, and by the OS if the process dies.

    Not re-entrant: taking it again while held (same or child process) waits on itself, so
    never nest it (or `analysis-chamber gpu`).
    """
    state_dir.mkdir(parents=True, exist_ok=True)
    deadline = None if timeout_s is None else time.monotonic() + timeout_s
    with open(state_dir / LOCK_FILE_NAME, "a+b") as handle:
        while True:
            try:
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                break
            except OSError:  # held by another process
                if deadline is not None and time.monotonic() >= deadline:
                    raise GpuLockTimeout(
                        f"GPU lock {state_dir / LOCK_FILE_NAME} not free after {timeout_s}s"
                    ) from None
                time.sleep(POLL_INTERVAL_S)
        try:
            yield
        finally:
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)


def run_locked(state_dir: Path, cmd: list[str]) -> int:
    """Run cmd while holding the GPU lock (waits forever) and return its exit code.

    cmd runs in a kill-on-close job, so if this wrapper is hard-killed the child dies too
    and cannot keep using the GPU after the lock frees. Raises OSError if cmd cannot start.
    """
    with gpu_lock(state_dir):
        job = KillOnCloseJob()
        try:
            child = subprocess.Popen(cmd)
            # shortcut: the child may spawn grandchildren before it joins the job (they then
            # escape); upgrade to CREATE_SUSPENDED if that ever matters.
            try:
                job.add(int(child._handle))  # noqa: SLF001 - Popen exposes no public handle
            except OSError:
                child.kill()  # an unjobbed child could outlive us and keep the GPU
                child.wait()
                raise
            return child.wait()
        finally:
            job.close()
