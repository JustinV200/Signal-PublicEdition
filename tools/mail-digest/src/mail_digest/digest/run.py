"""One digest run, start to finish: plan, run claude, guard the KB, update state, announce.

Planning (plan.py) searches the mail itself (mailbox/) and the model gets the
messages in its run context; after the guard, the runner picks what to announce from
the plans (notices.py, deadlines/). run_once takes its outside world (paths, the mail
tool, claude, notify, the board, the clock, git) as RunDeps (deps.py), so tests can
run it with fakes. The state's windows move forward only on a successful run (and
only for the accounts whose searches all succeeded), and announced keys are stored
only once the hub has queued the message (steps/outcome.py). A crash counts as a
failed run, so the failure alert fires, and so does a run with an edit the KB guard
couldn't check. That file is also flagged in the state and announced at once, and
every run after (crashed ones too) until git shows it has been reviewed. A claude
that raises isn't a crash: the guard still checks what it wrote. Every editable file
is flagged while claude runs, in case the run stops before the guard. A successful
run whose edits the guard didn't undo then emails the owner its digest
(digest_email/; a failure is only logged and spoken, the run still succeeds), and
every successful run refreshes the whiteboard's TODO view. It never commits: KB
edits stay in the working tree for an orchestrator to review.
"""

import logging
from dataclasses import replace

from mail_digest.claude import parse_result
from mail_digest.digest.deps import RunDeps
from mail_digest.digest.notices import due_items, is_success, run_notices
from mail_digest.digest.plan import RunPlan, plan_run
from mail_digest.digest.report import log_result
from mail_digest.digest_email import RunEdits, email_digest
from mail_digest.kb import expire_notes
from mail_digest.memory import advance_windows, record_failure, save_state
from mail_digest.settings import ACCOUNT_ALIASES
from mail_digest.steps import EditJob, announce_once, email_alert, record_crash, run_guarded_edit

log = logging.getLogger(__name__)


def run_once(deps: RunDeps, dry_run: bool = False) -> int:
    """One run (see the module docstring). Returns the exit code: 0 success, 1 failure.

    The caller holds the run lock. A claude that can't be found, can't start or
    raises is a failed run, and so is any crash (logged), so both count toward the
    failure alert. A dry run touches no state and lets its errors propagate. Raises
    OSError only if a crash can't be recorded in the state file.
    """
    if dry_run:
        plan = plan_run(deps, dry_run=True)
        log.info(
            "dry run, not starting claude.\ncommand: %s\ncontext:\n%s", plan.argv, plan.context
        )
        return 0
    try:
        return _run(deps)
    except Exception:
        log.exception("mail digest run crashed; counting it as a failed run")
        record_crash(deps.state_path, deps.notify, int(deps.now().timestamp()))
        return 1


def _run(deps: RunDeps) -> int:
    """A real run, start to finish. Raises on anything unexpected (run_once counts it)."""
    plan = plan_run(deps)
    # Before the snapshot, so the guard doesn't count the deletions as the model's edits.
    _expire_notes(deps, plan)
    job = EditJob(
        life_dir=deps.life_dir,
        state_path=deps.state_path,
        rejected_dir=deps.rejected_dir / plan.stamp,
        editable=plan.targets.editable,
        is_reviewed=deps.is_reviewed,
    )
    edit = run_guarded_edit(job, plan.state, lambda: deps.launch(plan.argv, plan.context))
    guard = edit.guard
    result = parse_result(edit.run, ACCOUNT_ALIASES)
    log_result(result)
    is_ok = is_success(result, guard)
    if is_ok:
        state = advance_windows(plan.state, plan.windows, plan.mail.completed)
    else:
        state = record_failure(plan.state)
    state = replace(state, needs_review=edit.needs_review)
    # Due items come from the plans by code, so a failed claude step still speaks them.
    notices = [*run_notices(plan, result, guard, state), *due_items(deps.life_dir, plan, guard)]
    # A run whose edit the guard undid may have been steered, so it sends no email. A
    # failed send never fails the run: its alert is spoken with the other announcements.
    edits = RunEdits(deps.life_dir, plan.today, plan.targets.editable, edit.before)
    if is_ok and not guard.reverted and not email_digest(edits, deps.send_email):
        notices = [email_alert(plan.run_start), *notices]
    save_state(deps.state_path, announce_once(state, notices, deps.notify, plan.run_start))
    if not is_ok:
        return 1
    deps.refresh_board()
    return 0


def _expire_notes(deps: RunDeps, plan: RunPlan) -> None:
    """Delete expired `Watch for (until ...)` lines from the course READMEs and the plan."""
    files = [*plan.targets.courses, *([plan.targets.plan] if plan.targets.plan else [])]
    for line in expire_notes(deps.life_dir, files, plan.today):
        log.info("removed expired note: %s", line)
