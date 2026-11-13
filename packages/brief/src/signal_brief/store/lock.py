"""The brief's lock: one writer at a time across every brief state file.

A thin wrapper over signal_jsonstate's state_lock on .state/events.lock, so
callers keep passing BriefPaths. BriefLogError is jsonstate's StateFileError
under the brief's old name, so every `except BriefLogError` also catches the
shared writer's failures.
"""

from collections.abc import Iterator
from contextlib import contextmanager

from signal_jsonstate import StateFileError
from signal_jsonstate import state_lock as _folder_lock

from signal_brief.paths import BriefPaths

# The brief's state couldn't be locked, read or written. Producers log it.
BriefLogError = StateFileError


@contextmanager
def state_lock(paths: BriefPaths) -> Iterator[None]:
    """Hold the brief's lock for the `with` block (up to 2 s). Not re-entrant.

    Raises:
        BriefLogError: Another writer held it too long, or it couldn't be opened.
    """
    with _folder_lock(paths.lock):
        yield
