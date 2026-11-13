"""One guarded claude run over life/: flag, snapshot, run claude, guard, and work out the flags.

Every runner that lets claude edit life/ (the mail digest, checker v2) calls this, so
the safety sequence is written once. It drops the flags git shows as reviewed, takes
the snapshot (stopping before claude if an editable file can't be read), saves every
editable file as flagged while claude runs (a run stopped before the guard leaves
unchecked edits), runs claude, and guards its edits straight away. The caller saves
the returned needs_review with the rest of its state, which unflags the files the
guard checked.
"""

import logging
from collections.abc import Callable
from dataclasses import dataclass, replace
from pathlib import Path

from mail_digest.claude import ClaudeRun
from mail_digest.kb import DIGEST_RULES, GuardReport, LineRules, fold_case, guard_edits, snapshot
from mail_digest.memory import DigestState, save_state

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class EditJob:
    """Where one guarded run edits, and how its edits are checked.

    rejected_dir is this run's own folder for undone edits (stamp included).
    is_reviewed(life_dir, path) says if a flagged file has been reviewed.
    rules are the guard's line rules (the digest's by default).
    """

    life_dir: Path
    state_path: Path
    rejected_dir: Path
    editable: tuple[str, ...]
    is_reviewed: Callable[[Path, str], bool]
    rules: LineRules = DIGEST_RULES


@dataclass(frozen=True)
class GuardedEdit:
    """What one guarded run produced.

    run: claude's run (an error, not a raise, if it couldn't start or raised).
    guard: the guard's report on its edits.
    before: the snapshot from before claude started (for the digest email).
    needs_review: the flags to save now: still-unreviewed files plus any the guard
      couldn't check.
    """

    run: ClaudeRun
    guard: GuardReport
    before: dict[str, bytes]
    needs_review: tuple[str, ...]


def run_guarded_edit(
    job: EditJob, state: DigestState, launch: Callable[[], ClaudeRun]
) -> GuardedEdit:
    """Run launch() under the KB guard (see the module docstring).

    state is the one loaded for this run; its needs_review is the old flags. Raises
    OSError if an editable file can't be snapshotted or the flags can't be saved, both
    before claude starts.
    """
    # Checked before claude starts, so this run's own edits don't keep a file flagged.
    unreviewed = _unreviewed(job, state.needs_review)
    before = _snapshot_before(job.life_dir, job.editable)
    # Flagged until the caller's save after the guard: a run stopped before then
    # (Ctrl+C, a kill, a crash) leaves unchecked edits. If this save fails, claude
    # never starts.
    flagged = tuple(sorted({*unreviewed, *job.editable}))
    save_state(job.state_path, replace(state, needs_review=flagged))
    run = _launch(launch)
    # Straight after claude, so nothing that could raise sits between its edits and the guard.
    guard = guard_edits(job.life_dir, before, job.editable, job.rejected_dir, job.rules)
    needs_review = tuple(sorted({*unreviewed, *guard.failed}))
    return GuardedEdit(run=run, guard=guard, before=before, needs_review=needs_review)


def _snapshot_before(life_dir: Path, editable: tuple[str, ...]) -> dict[str, bytes]:
    """life/ before claude starts. Raises OSError if an editable file isn't in it.

    The snapshot skips files it can't read, and the guard would take a skipped
    editable file for one the run created, and delete it if it broke the rules. So
    the run stops here instead, before claude starts. Names are compared ignoring
    ASCII case, as the guard does: Inbox.md on disk is the target inbox.md.
    """
    before = snapshot(life_dir, editable)
    names = {fold_case(path) for path in before}
    unread = [path for path in editable if fold_case(path) not in names]
    if unread:
        raise OSError(f"couldn't snapshot the editable files {unread}")
    return before


def _unreviewed(job: EditJob, flagged: tuple[str, ...]) -> tuple[str, ...]:
    """The flagged files that still haven't been reviewed (the rest are logged and dropped)."""
    pending = tuple(path for path in flagged if not job.is_reviewed(job.life_dir, path))
    for path in sorted(set(flagged) - set(pending)):
        log.info("%s has been reviewed; no longer announcing it", path)
    return pending


def _launch(launch: Callable[[], ClaudeRun]) -> ClaudeRun:
    """Run claude; one that can't start or raises is a failed run, not a crash.

    Claude may have edited life/ before it raised, so the guard must still run:
    as a crash, the edit would skip it and become the next run's baseline.
    """
    try:
        return launch()
    except Exception as error:
        log.exception("claude's run raised; counting it as a failed run")
        return ClaudeRun(error=f"claude's run raised {error!r}")
