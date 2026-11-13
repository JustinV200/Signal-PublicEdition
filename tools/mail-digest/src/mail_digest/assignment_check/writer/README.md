# assignment_check.writer

The locked-down claude that writes validated items into `life/`, and the budget that keeps it under the guard's limits.

## Public API

- `WRITER_LOCKDOWN`, `writer_command(claude_exe, editable)`, `writer_schema()` and `SITE_RULES` (`command.py`): v1's lockdown without mail, and the guard's `(site)` tag with `forbid_untick`.
- `open_lines(texts)`, and `select_items(items, lines)` returning `Selection(changes, adds, spilled)` (`budget.py`): at most `MAX_CHANGES` (4) existing lines changed per check, overdue first; the rest wait for the next check.
- `writer_context(now, targets, selection, problems)` and `problem_lines(problems)` (`context.py`), with `REASON_TEXT` for the problem wording.

## Dependencies

`mail_digest.claude`, `kb`, `settings`, `assignment_check.findings`, `courses`, `reader` (the frame tag), `signal_untrusted`.
