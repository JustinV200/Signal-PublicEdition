# mail_digest.digest_email

The email the owner gets after each successful run: this week's and next week's open todos, and the lines the run added or changed. The runner builds and sends it, never the model. Checker v2 is meant to call `build_digest_email` and `send_digest_email` the same way after its own checks.

## Public API (`from mail_digest.digest_email import ...`)

- `run_changes(life_dir, before, editable)` returns `{path: [lines]}`: each editable file's non-blank lines that were added or changed since the run's snapshot `before`, using the guard's own diff (`kb.added_lines`). It's read after the guard, so a file the guard undid has none. Files with no new lines are left out. Raises `OSError` if a file can't be read.
- `build_digest_email(life_dir, today, new_lines)` returns `DigestEmail(subject, body)`. The subject is `Signal digest <YYYY-MM-DD>`. The plain-text body has a one-line note that `(mail)` lines came from email, then the open `- [ ]` lines of this week's plan and next week's (`(no plan yet)` if that week isn't rolled over), then `new_lines` by file (`(none)` if there are none). A body over 50,000 chars is cut at a line break with a note, so it stays under send-self's own cap. Raises `OSError` or `UnicodeDecodeError` if a plan can't be read.
- `send_digest_email(email)` writes the body to `.state/digest-email.txt` (overwritten each run) and runs `uv run --project tools/mail --frozen --no-sync mail send-self --subject=... --body-file ...` once through `child_env.run_hidden` (hidden window, clean env, 60 s timeout). Returns True only on exit 0. Never raises.

## Files

`build.py`, `changes.py`, `send.py`.

## Dependencies

`mail_digest.kb` (plan lookup, the diff, case folding), `mail_digest.child_env`, `mail_digest.settings`. Standard library only. At run time it needs the mail tool's venv and its `alt` sign-in (`owner.alt@example.com`).
