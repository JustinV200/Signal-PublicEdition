# mail_digest.steps

The run steps both runners that edit `life/` share: the mail digest (`digest/`) and the assignment checker (`assignment_check/`).

## Public API (`from mail_digest.steps import ...`)

- `start_background_run(lock_path, argv=None, name="mail digest", log_path=LOG_PATH)` (`background.py`): `--now`. Starts `background_command(module)` (`pythonw -m <module>`) detached unless the shared run lock is held, and prints one line either way.
- `run_guarded_edit(EditJob, state, launch)` returns `GuardedEdit(run, guard, before, needs_review)` (`guarded_edit.py`): drop reviewed flags, snapshot, flag every editable file, run claude, guard its edits with `EditJob.rules`. The caller saves `needs_review`.
- `announce_once(state, notices, notify, now, closing="", name="mail digest")` (`outcome.py`): speaks what's new once, with an always-spoken closing line, and stores the keys only once the hub queued them. Items the hub didn't take go to the state's `pending` list and are spoken first (after the run's one-run alerts) on later runs, for up to `PENDING_KEEP_S`. `record_crash(state_path, notify, run_start)` is the digest's crash path, and `STATE_UNUSABLE` its sentence.
- `kb_alerts(guard, state, run_start, name="mail digest")`, `email_alert(run_start, name=...)`, `failure_alert`, `signin_reminders` and `gap_notices` (`notices.py`): the runner's own announcements.
- `roll_week(life_dir, today, dry_run=False)` returns `WeekRoll(status, notice)` (`rollover.py`): rolls `life/` over to today's week (`mail_digest.rollover`) at the start of a run, before anything reads the week. Never raises: a failure is logged, the run goes on, and the status is `failed`. On a failure or a week between terms, `notice` is an announcement keyed `rollover|<week>|failed` or `rollover|<week>|term` (so it's spoken once a week at most); the between-terms one says to add the next term's folder with a `Term dates` line. Both runners speak it first with their other announcements. A dry run has no notice.
- `refresh_todo_board()` (`todo_board.py`): `whiteboard todo sync --if-running`, best effort.
- `setup_logging(log_path)` (`logs.py`): the rotating log file, plus stderr when there is one.

## Files

`background.py`, `guarded_edit.py`, `outcome.py`, `notices.py`, `rollover.py`, `todo_board.py`, `logs.py`.

## Dependencies

`mail_digest.settings`, `child_env`, `announce`, `claude`, `kb`, `mailbox` (the `AccountProblem` type), `memory`, `rollover`. Standard library only.
