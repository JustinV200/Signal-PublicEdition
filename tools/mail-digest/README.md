# mail-digest

A scheduled job that reads the owner's three Gmail accounts (mail tool aliases `personal`, `alt` and `school`) and keeps `life/` current:

- Class deadlines, assignments and announcements go into the course README and this week's plan.
- Overdue or late work goes under `## Overdue` at the top of this week's plan.
- Anything else notable goes into `life/inbox.md`.
- Before anything else, each run starts the new week if it hasn't been started: the new week's folder and plan from the week templates (`life/templates/week-*.md`, or built-in defaults), with last week's open todos and Overdue carried over, and last week's review counts filled in. This is code, not the model. A failed rollover, or a week that falls between terms, is spoken once a week. See [src/mail_digest/rollover/README.md](src/mail_digest/rollover/README.md).
- Every line it adds or changes ends in ` (mail)`. Those lines are email-derived data, never instructions.
- Urgent items are spoken once through audiohub: things due within 24 hours, newly overdue work, accounts that need signing in again, and the runner's own alerts. The runner speaks them, not the model.
- After each successful run the runner emails the owner (at the mail tool's `SELF_ADDRESS`, subject `Signal digest <date>`) this week's and next week's open todos and the lines the run added or changed. See [Digest email](#digest-email).

It runs once a day at 07:00 as a per-user Windows scheduled task, and on demand with `mail-digest --now`. Each run is one headless, locked-down `claude -p` that follows the routine in [refdocs/routines/mail-digest.md](../../refdocs/routines/mail-digest.md), with the line rules and KB conventions it shares with the assignment checker ([refdocs/routines/kb-line-rules.md](../../refdocs/routines/kb-line-rules.md)) appended by the runner into `.state/prompts/mail-digest.md` just before claude starts.

Code and model split the work ("a mix of AI and code"):

- **The runner's code** lists the accounts, searches each `ok` account's window with paging and works out which accounts completed (`src/mail_digest/mailbox/`), then hands the model the messages it found in the run context. After the run it picks what's due within 24 hours or overdue from the week plans, with stable keys (`src/mail_digest/deadlines/`), and speaks those.
- **The model** reads and triages the mail (`mail_read`, `mail_thread`), decides what matters, writes the KB lines and the summary, and flags emails that tried to steer it.

**It never commits.** KB edits stay in the working tree. An orchestrator session reviews `git diff life/` and commits them.

## Scheduled runs never trigger Duo

The owner is asleep at 07:00 and can't approve a Duo push. So the scheduled run is email-only:

- It reads mail through the mail tool's saved Gmail API sign-ins, which need no Duo.
- It never uses a browser and never logs in to the school, CAS, Moodle or Google Classroom. The job has no browser tools at all (`--strict-mcp-config` loads only the mail server).

On-demand runs (`--now`) are started by the owner, so they may involve Duo later, when the owner is there to approve it. Today `--now` does exactly what the scheduled run does.

The browser check of Moodle and Google Classroom is the assignment checker, `assignment-check`, in this same project ([src/mail_digest/assignment_check/README.md](src/mail_digest/assignment_check/README.md)). It's on demand only, started by the owner, may log in to Moodle through the vault plus Duo, and is never part of the scheduled run. It shares this job's run lock, state file and KB guard, and tags its lines ` (site)`.

## Setup (owner)

1. Sign in the mail accounts: [tools/mail/SETUP.md](../mail/SETUP.md). Then `uv run --project tools/mail mail accounts` should show each alias as `ok`. That also syncs the mail tool's venv, which the job's MCP server and the digest email's `mail send-self` run with `--no-sync`. The job digests the aliases `personal`, `alt` and `school`; one you never add (for example if a school blocks the app) is skipped. The digest email needs the account whose address is the mail tool's `SELF_ADDRESS` (your Gmail address; setup signs it in as `personal`), which it's sent from and to.
2. Create the job's venv from the repo root: `uv sync --project tools/mail-digest --frozen`. Runs use `--no-sync`, so they never install anything: do this again after the dependencies change. A no-sync run on a missing venv just creates an empty one and fails, so `register.ps1` checks that the job imports and refuses to register if it doesn't. The audiohub venv comes from setting up the hub.
3. Register the task from the repo root. No admin is needed:
   ```powershell
   .\tools\mail-digest\register.ps1 -WhatIf   # show what it would do
   .\tools\mail-digest\register.ps1 -RunNow   # register, then run once now
   .\tools\mail-digest\unregister.ps1         # remove it again
   ```
   The time and task name are in `schedule.psd1`. To change them, edit that file and run `register.ps1` again. The trigger is stored as local time, so it stays at 07:00 across DST changes.

The task runs only while you're logged on, because the mail sign-ins are DPAPI-encrypted for your Windows user. A run missed while the PC was asleep starts when it wakes.

## Running by hand

From the repo root:

```
uv run --project tools/mail-digest --frozen --no-sync mail-digest --now       # start a run in the background, return at once
uv run --project tools/mail-digest --frozen --no-sync mail-digest             # a run in the foreground, logging to the console too
uv run --project tools/mail-digest --frozen --no-sync mail-digest --dry-run   # print the command and run context only
uv run --project tools/mail-digest --frozen --no-sync mail-digest rollover --dry-run   # show what starting this week would write
uv run --project tools/mail-digest --frozen --no-sync mail-digest rollover             # start this week now (takes the run lock)
```

`--now` is the one for a voice session or another agent: it starts `pythonw -m mail_digest` detached and returns. Only one run can go at a time (a lock in `.state/run.lock`, released by the OS even if a run crashes), so `--now` refuses while the scheduled run is going, and a second run started by hand exits with an error.

The log is `tools/mail-digest/.state/mail-digest.log`. It rotates at 1 MB. Each run logs:

- its windows, the completed accounts and their message counts, the claude version, the cost, the due and overdue keys and the summary;
- any tool call the lockdown refused, and any email the model flagged as suspicious (account, message id, sender). Either one is a prompt bug or an email trying to steer the job, so read that mail;
- accounts that weren't searched, mail skipped by the lookback cap, and KB edits the guard undid.

Everything the model wrote is logged with `%r`, so an email can't forge log lines. claude's stderr is in `.state/claude-stderr.log` (overwritten each run).

## Lockdown

Emails are attacker-controlled input, so the flags enforce the limits, not the prompt (`src/mail_digest/claude/command.py`):

| Flag | Effect |
|---|---|
| cwd `life/` + `--restricted` | Ignores user, project and local settings files (so `.claude/settings.local.json`'s `bypassPermissions` never applies), refuses bypassPermissions, and confines Read and Edit to `life/`. AGENTS.md and CLAUDE.md aren't loaded either |
| `--permission-mode dontAsk` + `--permission-prompts none` | Anything not allowed is denied, and nobody is asked |
| `--tools Read,Edit` | No Bash, PowerShell, Write, web or subagents |
| `--allowedTools` | `Read`; `Edit(/<path>)` for each exact file of this run (`inbox.md`, this week's plan, each current course README), built at run time and only for plain files that exist (a rule for a missing file would also cover a folder of that name); `mail_read` and `mail_thread` |
| `--disallowedTools` | Also denies Bash, PowerShell, Write, the web tools and Agent, plus `mail_draft` and `mail_send_draft`, and `mail_accounts` and `mail_search` (the runner searches itself) |
| `--strict-mcp-config --mcp-config mcp.json` | Only the mail server. No audiohub, browser, sessions, whiteboard or claude.ai connectors |
| `--max-budget-usd 2.00`, 30-min kill | Caps a runaway run. The kill takes claude's whole process tree, MCP servers included |

The leading `/` anchors each Edit rule to `life/`. Without it, `Edit(inbox.md)` also matched `me/inbox.md`, and the old `*` patterns let the model create course or plan files that would have redirected later runs.

The output is `--output-format stream-json`. Before the model acts, the runner checks the `init` event and kills the run unless the permission mode is `dontAsk`, the tools are exactly Read, Edit, StructuredOutput, `mail_read` and `mail_thread`, the only MCP server is `mail: connected`, the cwd is `life/` and there are no additional directories. So a Claude Code update that changes a flag's behavior stops the job instead of loosening it. A claude still running when its output ends is killed too.

The runner also drops a parent Claude session's environment variables (`CLAUDECODE`, `CLAUDE_CODE_*`, ...), so a run started from inside a Claude session acts the same as a scheduled one.

Checked by hand on Claude Code 2.1.301 (2026-10-19) with harmless prompts, when the model still had all four mail read tools (TODO: re-check the init event now that `mail_accounts` and `mail_search` are denied; a mismatch only stops the run). The four mail tools were disallowed for the probes, so no mail was read:

- The exact argv's init event passed the runner's check (claude was killed at init, before the model's first turn).
- From the real `life/`:
  - Read `README.md`: allowed.
  - Read `../.gitignore` or `C:\src\Signal\.mcp.json`: denied.
  - Edit-create `me/inbox.md`, `../refdocs/probe-nope.md` or a fake course README: denied.
  - Bash, PowerShell, Write, web, audiohub and `mail_draft`: not available.
  - `life/` was byte-for-byte unchanged afterwards.
- On a scratch copy of `life/`, Edit on `inbox.md` and this week's plan were allowed. Edit on `README.md`, and creating `me/inbox.md`, next week's plan or a fake course README, were denied.

Re-check them after a big Claude Code update, since flag behavior can change.

## KB guard

After every run that starts claude (failed ones too, even if the launch raised) the runner diffs `life/` against a snapshot taken before claude started (`src/mail_digest/kb/`). Links and junctions are left out of the snapshot, and so is a file that can't be read (logged). An editable file that can't be read stops the run before claude starts, and one that's there but can't be read after the run is a guard failure (below). Only the editable files are kept as bytes, the rest as SHA-256 digests. Paths are compared ignoring ASCII case, as NTFS and Claude Code's Edit rules do: an Edit through `INBOX.MD` is allowed by `Edit(/inbox.md)` and leaves the file renamed `INBOX.MD`. Look-alikes such as the Kelvin sign for `k` count as other names, as they do for NTFS and the Edit rules.

- **An editable file, in any case.** That's the job's work. Every added line must end in ` (mail)` (only the routine's `## Overdue`, `## Coming up` and `## For the <week> plan` headings are exempt), be at most 300 chars, and use only allowed characters: letters, marks and digits of any script, the plain space, the no-break spaces U+00A0 and U+202F, and basic punctuation and signs (`. , : ; ! ? - ' " ( ) / % # & @ + * | [ ] _ =`, en and em dashes, curly quotes, the no-break hyphen and `… • · → € £ ° ® ™`, none of which means anything in Markdown). This is an allowlist, because each deny-list round found another Markdown trick for hiding text. So there's no backslash (escapes), backtick (code), `<` or `>` (HTML, comments, autolinks), `{`, `}`, `^` or `~` (math, footnotes, fences), `$` (math, where `%` hides the rest of the line), emoji or other symbol, and no hidden character: tab, control, format and unassigned characters, other spaces and line breaks other than `\n` all fail, as do allowed letters and marks that render as nothing (variation selectors, Hangul fillers and the like), overlay marks (U+0336 and the like, which fake a strikethrough and make a todo look crossed out), enclosing marks (U+20E0 and the like, a "no" sign that makes an item look cancelled) and more than 3 marks in a row (stacked marks spill over the lines around them). A line also can't contain a URL (any `//`, so `https://` and a scheme-less `//host`, or `www.`), Markdown link or image (`](`), link definition (any `]:`, which also covers the Markdown comment `[//]: # (...)` and a definition hidden in a list item or quote), character reference (`&#` or a named one such as `&zwnj;`, which can decode to a hidden character or a `/`) or number of 6+ digits. An added table row can't have more cells than its table's header, because GFM and VS Code drop the extra cells, and the text in them, when they render. The tag counts as a cell, so a row carries it in its last cell (`| Wed 2026-11-04 | Final exam | 25% (mail)`). Rows are trimmed of ASCII spaces and tabs only, as GFM trims them, so a leading no-break space is a cell. A delimiter row needs no `|`: in GFM one with a `:` (`:---`) makes a 1-cell table under any header line, and VS Code takes `:---` or `---` under a header with a `|`, so every such line counts as one. Two tables with no blank line between are one table to the renderers, with the first one's width, so a delimiter row inside an open table can only narrow the width (removing a blank line is otherwise free). A list item or heading straight after a table counts as a row too. Both of these are stricter than the renderers, the safe direction. Bare domains, digits split by spaces, digits that aren't decimal digits (circled or superscript ones don't count toward the 6) and email addresses (GFM links them, `mailto:` and `xmpp:` forms too) still get through, a known gap. At most 60 lines may be added (blank ones included) and 5 non-blank lines removed, and a changed line counts as both, so at most 5 existing lines can change (ticking a todo is one). The routine puts the rest of a big catch-up in `inbox.md` as new lines. A file that had any HTML before the run (a `<` followed by a letter, `!`, `?` or `/`: `<!--`, `<details>`, any other tag, an autolink or a placeholder such as `<date>`) takes no edits at all, since an added line could land inside a hidden comment or block; no target file has any `<` today. Nor does a file with a lone `\r`, which GFM takes for a line break that the guard (splitting on `\n` only) doesn't see. A file that breaks a rule is saved to `.state/rejected/<run stamp>/` and restored. A file whose name only changed case is renamed back, unless another file already has the old name (logged).
- **Anything under an editable path** (`inbox.md/x.md`). The job's work too, since Edit rules match gitignore-style. It's saved to the rejected folder and undone (a new file is deleted, with its empty folders).
- **Any other change.** The Edit rules mean the job can't have made it, so it's the owner's or another agent's concurrent work. It's logged and left alone, since reverting would destroy that work, and the run announces that other files changed.

An undo or another change is announced, and that run's due and overdue items aren't spoken, since an email may have steered it. The search windows still move forward after an undo, so the next run doesn't fetch that mail again: the undone file's items survive only in `.state/rejected/`. The guard checks every editable file even if one fails. A file it couldn't check (there but unreadable, or a save, restore or rename that failed) may hold an unchecked edit, which the next run would take as its baseline. So that run fails (its windows stay put), and the file is flagged in `.state/state.json`: a review alert naming it is spoken that run and every run after, until `git status` shows it committed or reverted (checked before claude starts). Every editable file is flagged like this before claude starts, and only the state save after the guard clears it. So a run stopped or crashed in between (Ctrl+C, a hard kill, a crash after the guard) leaves them all flagged, and their unchecked edits are announced too. The guard restores the whole file, so an owner edit made to that same file during the run is undone too. It's kept in the rejected copy.

## Announcements

The model can't speak and doesn't pick what's spoken. After the run the runner picks the due and overdue items from this week's plan (last week's if the run couldn't roll the week over) and next week's (`deadlines/`): every open todo whose `(due YYYY-MM-DD[ HH:MM])` marker is within the next 24 hours (no time means 23:59), as `due|<YYYY-MM-DD>|<slug>`, and every open todo under `## Overdue`, as `overdue|<slug>`. The slug is the todo's tag and name without its parentheticals, so a new note or a new time on the same day keeps the key, while the due day in the key lets a weekly todo with the same name be spoken each week. Keys made before the due day was added don't match, so on the first run after that change the items due within 24 hours are spoken once more (at most that day's items, once). The due items come from the plans by code, so they're spoken on a failed run too, unless the guard undid, found or couldn't check an edit. Then the runner:

1. Collects candidates in this order, its alerts first so the due items can't push them out:
   - a reset alert on the run that found `.state/state.json` corrupt and started fresh (its review flags are gone, so check `git diff life/`), then a review alert every run while a file the guard couldn't check is flagged, then a guard alert if it undid an edit, and a notice if other `life/` files changed during the run. A run that can't read the state file at all just says so (there's no state to key it by) and stops;
   - on a failed run, a failure alert every second consecutive failure. A crash, or an edit the guard couldn't check, counts as a failed run too;
   - on a successful run, an email alert first if the digest email couldn't be built or sent, then sign-in reminders (an account that `needs re-auth` or has an `error`, at most weekly; `offline` is only logged) and search reminders (an account whose search failed or hit its cap, at most weekly), then a notice for mail the 3-day lookback cap skipped, then the due and overdue items (none if the guard undid an edit or other files changed).
   - on a failed run, the due and overdue items too, after the failure alert (none if the guard undid, found or couldn't check an edit).
2. Drops keys already announced in the last 30 days.
3. Speaks the first 3 and sums up the rest as "Plus N more". In the due items (whose text may come from email), URLs and markup are stripped, any sentence with a domain, an `@` or a 6+ digit number (spaces ignored) is dropped, and each item is cut to about 120 chars.
4. Calls `uv run --project tools/audiohub --frozen --no-sync audiohub notify --source mail-digest --priority high -- TEXT` once.
5. Stores the spoken items' keys only if that exits 0, so a hub that's down means a retry for these, but the one-run alerts (reset, guard, other changes, failure, email) aren't retried. Summed-up items aren't stored, so they can be spoken on a later run.

## Digest email

After a successful run whose edits the guard didn't undo (`src/mail_digest/digest_email/`), the runner, never the model:

1. Diffs each editable file against the snapshot taken before claude started, with the guard's own diff. It runs after the guard, so only lines that passed the line rules are left (a file the guard undid has none).
2. Builds a plain-text email from `life/`. The subject is `Signal digest <YYYY-MM-DD>`. The body has a note that `(mail)` lines came from email, then the open `- [ ]` lines of this week's plan and of next week's (`(no plan yet)` before the rollover), then the run's new lines by file. A body over 50,000 chars is cut at a line break, with a note.
3. Writes the body to `.state/digest-email.txt` (overwritten each run) and runs `uv run --project tools/mail --frozen --no-sync mail send-self --subject=... --body-file ...` once (hidden, 60 s timeout). `send-self` only ever mails the mail tool's `SELF_ADDRESS` from the account with that address, so it needs no Allow dialog ([tools/mail/README.md](../mail/README.md#security)).

Both the scheduled run and `--now` send it, and a dry run doesn't. A run that failed, or whose edit the guard undid or couldn't check, sends none. A failure to build or send never fails the run: it's logged, and the email alert is spoken once with that run's other announcements. The assignment checker sends the same email after a successful check that ran its writer.

After a successful run the runner also refreshes the whiteboard's TODO view with `uv run --frozen --no-sync --project tools/whiteboard whiteboard todo sync --if-running` (hidden, 30 s timeout). It does nothing if the whiteboard isn't running, and a failure is only logged.

## No duplicates

`.state/state.json` is gitignored. Only the runner writes it, and nothing in it is shown to the model.

- **Windows**: each account is searched `after:<searched_until - 5 min> before:<run start>` (Unix seconds, Gmail receive time). The small overlap catches mail stamped at the boundary, and the routine skips items already in the KB. Pages of 50 go back from the newest by date until one comes back short (about one search per 45 messages), and messages are kept once by id. An account's window moves forward only if all its searches succeeded (at most 40 per run); one that failed or hit the cap is spoken as a problem at most weekly. An offline account is retried next run, looking back at most 3 days (2 on its first run); the runner warns and announces once when that cap skips mail.
- **Announced items**: the runner keys each one itself (`overdue|<slug>`, `signin|<alias>|<week>`, ...). Keys must match a strict pattern and at most 500 are kept.
- **KB lines**: the routine reads a file before editing it and updates an existing line rather than adding a second one.

The model's structured output (`suspicious` and `summary` only) is validated in `claude/result.py`. Only known aliases are kept, ids and senders must match strict patterns, the list is capped, and a failed or malformed run leaves the windows untouched.

## Layout

`src/mail_digest/`:

| Path | Does |
|---|---|
| `digest/` | The digest's runner: `cli.py` (`mail-digest [--now \| --dry-run]`: flags, logging, the run lock), `run.py` (`run_once(deps)`: one run, start to finish), `deps.py` (`RunDeps`, its injectable outside world: the mail tool, claude, notify, the mail sender, the board, the clock, git), `plan.py` (the plan made before claude starts, mail search included), `notices.py` (what a run announces, due items included) and `report.py` (logs the windows, the mail and the result) |
| `rollover/` | Starts each new week in `life/` by code: the folder, plan, log, review and workspace, with the open todos carried over (its own README) |
| `steps/` | The steps both runners share: `guarded_edit.py` (drop reviewed flags, snapshot, flag the editable files, run claude, guard its edits), `background.py` (`--now`), `notices.py` (the runner's own announcements), `outcome.py` (speaks a run's announcements once, records a crash), `todo_board.py`, `rollover.py` (the week rollover at the start of a run), `logs.py` |
| `assignment_check/` | Checker v2, `assignment-check`: the on-demand course-site check (its own README) |
| `child_env.py` | Clean environment and hidden window for child processes, a quiet runner for helper CLIs, and the tree kill that ends a helper CLI at its timeout, and claude (with its MCP servers) at its timeout, on a bad init event or when its output ends |
| `settings.py` | Accounts, model, budget, lookbacks, caps, paths |
| `claude/` | The argv, launcher and init check, schema, result parser, run context |
| `mailbox/` | Routine step 2 in code: the account check, the paged search and the completed accounts, through the mail tool's CLI |
| `deadlines/` | Routine step 5 in code: the due and overdue todos to announce, with stable keys |
| `memory/` | The state file and the run lock |
| `kb/` | The editable files, the snapshot, the post-run guard and the git review check |
| `announce/` | Composing the message, and the audiohub CLI call |
| `digest_email/` | The owner's digest email: the run's new lines, the email built from `life/`, and the `mail send-self` call (both runners send it) |

Each subfolder has its own README.

Other files:

- `mcp.json`: the job's MCP config (the mail server only). Its paths are relative to `life/`.
- `schedule.psd1`, `register.ps1`, `unregister.ps1`: the scheduled task.

It uses only the standard library, plus `signal-untrusted` (`packages/untrusted`, also stdlib only) for the checker's data frame. Claude Code itself comes from PATH or the VS Code extension.

## Development

```
uv run pytest
uv run ruff check src tests
uv run ruff format src tests
```

The tests cover the week rollover (carry-over, idempotency, catch-up, term boundaries), the windows and dedupe, the paged search and completed accounts (a fake mail tool), the due and overdue picks, the lock, result validation and spoken text, the KB lookup and guard, the lockdown flags and init check, the runner's notices and the announcement cap, the digest email's content, and `run_once` with a fake mail tool, claude, notify, mail sender and board. For the checker: the findings security table, the reader and writer lockdowns, the 4-change budget, the visit out file, and `run_check` with fake visits, claudes, notify, mail sender and board. They never start claude, send a notification or send mail (a launcher test and a helper-timeout test run stand-in Python processes, and the review check test runs git in a temp repo).
