# mail_digest.digest

The mail digest's own runner: the `mail-digest` CLI (`cli.py`), one run start to finish (`run.py`), its outside world (`deps.py`), the plan made before claude starts (`plan.py`), what a run announces (`notices.py`), and its result log (`report.py`). The project README says what a run does.

## Public API (`from mail_digest.digest import ...`)

- `main(argv=None)`: `mail-digest [--now | --dry-run]`.
- `run_once(deps, dry_run=False)` with `RunDeps` (`default_deps()` for the real world, whose `mail` is the mail tool's CLI): one run, exit code 0 or 1. It searches the mail before claude starts (a dry run does too, read-only) and picks the due and overdue items after the guard, on a failed run too, unless the guard undid, found or couldn't check an edit.

## Dependencies

`mail_digest.steps`, `claude`, `kb`, `mailbox`, `deadlines`, `memory`, `announce`, `digest_email`, `settings`.
