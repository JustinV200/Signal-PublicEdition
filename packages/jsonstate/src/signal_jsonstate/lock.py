"""A cross-process lock on a state folder: one writer at a time.

A Windows byte-range lock (msvcrt.locking) on a lock file the caller names. The
OS drops it when the process exits, even on a crash, so it's never left stale.
It isn't re-entrant: code that already holds it must not take it again.
"""

import msvcrt
import os
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

LOCK_WAIT_S = 2.0
LOCK_POLL_S = 0.02


class StateFileError(RuntimeError):
    """A state file couldn't be locked, read or written."""


@contextmanager
def state_lock(lock_path: Path) -> Iterator[None]:
    """Hold the lock on `lock_path` for the `with` block, waiting up to LOCK_WAIT_S.

    Args:
        lock_path: The lock file; it and its folder are created if missing.

    Raises:
        StateFileError: Another writer held it past LOCK_WAIT_S, or the lock file
            couldn't be opened.
    """
    try:
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(lock_path, os.O_RDWR | os.O_CREAT)
    except OSError as error:
        raise StateFileError(f"can't open {lock_path}: {error}") from error
    try:
        _acquire(fd, lock_path)
        try:
            yield
        finally:
            os.lseek(fd, 0, os.SEEK_SET)
            msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
    finally:
        os.close(fd)


def _acquire(fd: int, lock_path: Path) -> None:
    """Lock one byte at offset 0, polling until LOCK_WAIT_S runs out."""
    deadline = time.monotonic() + LOCK_WAIT_S
    while True:
        try:
            # LK_NBLCK fails at once when held; LK_LOCK would retry for 10 s.
            msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
            return
        except OSError as error:
            if time.monotonic() >= deadline:
                raise StateFileError(
                    f"{lock_path.name} held by another writer for over {LOCK_WAIT_S} s"
                ) from error
        time.sleep(LOCK_POLL_S)
