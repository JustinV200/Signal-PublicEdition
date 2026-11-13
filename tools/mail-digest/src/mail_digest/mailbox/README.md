# mail_digest.mailbox

Step 2 of the mail digest routine, done by the runner instead of the model: list the accounts, search each `ok` account's window with paging, and say which accounts completed. The model gets the messages in its run context and only reads and triages them.

## Public API (`from mail_digest.mailbox import ...`)

- `gather_mail(client, windows)` returns `GatheredMail(messages, completed, problems)`.
  - An alias the mail tool doesn't list is skipped quietly. One whose status isn't `ok` becomes an `AccountProblem(alias, status)` (the runner speaks a sign-in reminder for `needs re-auth` and `error`).
  - Each `ok` account's window is searched with `after:<after> before:<before>` and 50 results a page, newest first. While a page comes back with 45 or more (the mail tool drops messages deleted mid-search, so a slightly short page may still mean more), the next search ends a minute after the oldest date on it (dates are to the minute). Pages overlap by that minute and messages are kept once by id, so it takes about one search per 45 messages.
  - A failed search, a full page that can't move back (no dates, or 50 messages in one minute), or more than 40 searches for one account leaves the account out of `completed` with none of its messages, so its window doesn't move and the next run fetches it again. It's also an `AccountProblem(alias, SEARCH_FAILED)`, which the runner speaks at most weekly.
  - Raises `MailToolError` if the accounts can't be listed at all (the run then fails).
- `MailClient`: the `accounts()` and `search(alias, query, max_results)` interface, faked in tests.
- `CliMailClient(command=MAIL_COMMAND)`: the real one, running `mail accounts` and `mail search` from `tools/mail` (`uv run --frozen --no-sync`, hidden, 120 s timeout, with `PYTHONIOENCODING=utf-8` from `child_env` so non-ASCII mail isn't garbled). An account row is read from its start (alias, email, status), so odd detail text after it can't hide the status. Search results keep only `id`, `thread_id`, `date`, `from`, `to`, `subject`, `snippet` and `labels`; the mail tool has already wrapped the email-derived ones in `<untrusted_email_content>`.

## Files

`client.py`, `gather.py`.

## Dependencies

`mail_digest.settings`, `mail_digest.child_env`, `mail_digest.memory` (the `Window` type). Standard library only.
