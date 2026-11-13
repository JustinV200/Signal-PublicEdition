# mail_digest.assignment_check

Checker v2 (`refdocs/research/checker-v2.md`): an on-demand read of the owner's course sites (Moodle and Google Classroom) into `life/`. Only the owner starts it, and it's never scheduled.

## Command

From the repo root:

```
uv run --project tools/mail-digest --frozen --no-sync assignment-check --now      # start a check in the background
uv run --project tools/mail-digest --frozen --no-sync assignment-check            # a check in the foreground, printing items and links
uv run --project tools/mail-digest --frozen --no-sync assignment-check --dry-run  # print both plans and every argv; starts nothing
uv run --project tools/mail-digest --frozen --no-sync assignment-check --sign-in-test  # open each site's first page once
```

## Config

Your sites and courses live in `tools/mail-digest/assignment-check.toml` (gitignored), loaded and checked by `check_config.py`: the Moodle and Classroom base URLs (https only), the school Google account, and one `"tag:id"` (Moodle) or `"tag:id:class name"` (Classroom) entry per course. The browser side lives in `tools/browser/browser-checker-moodle.toml` and `browser-checker-classroom.toml` (also gitignored). `setup mail-digest` copies all three from their `*.example.toml` files, asks for every value, then offers `--sign-in-test`. Duo is yours alone: the visit waits while you approve on your phone, and nothing ever types a code.

The voice brain runs the `--now` form when the owner asks to check the owner's assignments. The log is `tools/mail-digest/.state/assignment-check/assignment-check.log`.

## What a check does

1. **Visit** (`visit.py`, `courses.py`): `browser-tool-visit` twice under the shared run lock, Classroom then Moodle, each with its own config in `tools/browser` and its plan and out files in `.state/assignment-check/`. Each launch is killed after `VISIT_TIMEOUT_S` (15 min). A stale out file is deleted first, and a missing or malformed one is an error. A busy launch (the checker's browser is open) or a failed one stops the check before any claude runs.
2. **Read** (`reader/`): one `claude -p` per site with ok pages, Moodle first, with `--tools ""`, no MCP servers, `--restricted` in the empty `.state/assignment-check/reader/`, a $1.00 budget and a 10-minute kill. Its init event must list exactly `StructuredOutput`. Its context is capped at `MAX_READER_CHARS` by whole pages. A failed reader stops the check.
3. **Check** (`findings/`, pure): page, name, ref, class, account, kind, due, status and caps, all against the visit's own page text. A course with any page problem is left out of the check.
4. **Write** (`writer/`): the 4-change budget picks the items, then v1's locked-down claude without mail (Read and exact Edits in `life/`, no MCP servers) writes them, through the guard with the `(site)` tag and no unticking. It's skipped when there's nothing to do. By design, a due date that changed on a site isn't written into an existing line (that would spend the change budget); only status changes, overdue moves and new items are.
5. **After**: the announcements (`notices.py`, source `assignment-check`), always ending with a done line; then on success the self-only digest email (unless the guard undid an edit) and the whiteboard's TODO view. `last-check.json` holds every item with its link (`report.py`).

It shares `.state/run.lock`, `state.json`'s review flags and announced keys, and the KB guard with the digest, and never touches the digest's search windows or failure count. It never commits.

## Public API (`from mail_digest.assignment_check import ...`)

- `main(argv=None)`: the CLI.
- `run_check(deps)` with `CheckDeps` returns `CheckOutcome(exit_code, lines)`. `live.default_deps()` is the real world.

## Files

`cli.py`, `live.py` (the real deps and the dry run), `run.py`, `gather.py` (visits and readers), `courses.py`, `check_config.py` (the config file), `sign_in_test.py`, `visit.py`, `notices.py`, `report.py`, and the `reader/`, `findings/` and `writer/` packages.

## Dependencies

`mail_digest.claude`, `kb`, `memory`, `steps`, `announce`, `digest_email`, `settings` and `child_env`; `tools/browser`'s `browser-tool-visit` command (run as a process); `signal_untrusted` (`packages/untrusted`).
