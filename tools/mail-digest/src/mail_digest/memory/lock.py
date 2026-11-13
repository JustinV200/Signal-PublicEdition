"""The run lock: one digest run at a time, so a hand run and a scheduled run can't overlap.

A Windows byte-range lock (msvcrt.locking) on .state/run.lock. The OS drops it when
the process exits, even on a crash, so a lock is never left stale.
"""

import msvcrt
import os
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path


class LockHeldError(RuntimeError):
    """Another digest run holds the lock."""


@contextmanager
def run_lock(path: Path) -> Iterator[None]:
    """Hold the run lock for the `with` block.

    Raises LockHeldError at once (no waiting) if another run holds it, and OSError
    if the lock file can't be opened.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_RDWR | os.O_CREAT)
    try:
        try:
            # Locks one byte at the file position (0). Windows allows locking past EOF.
            msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
        except OSError as error:
            raise LockHeldError(f"{path} is held by another digest run") from error
        try:
            yield
        finally:
            os.lseek(fd, 0, os.SEEK_SET)
            msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
    finally:
        os.close(fd)


def is_locked(path: Path) -> bool:
    """True if another run holds the lock right now."""
    try:
        with run_lock(path):
            return False
    except LockHeldError:
        return True
