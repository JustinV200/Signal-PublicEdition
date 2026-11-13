# mail_digest.claude

Builds, runs and checks one locked-down `claude -p` process, and validates what it returns.

## Public API (`from mail_digest.claude import ...`)

- `Lockdown` (`lockdown.py`): one run's tools, extra allow rules, deny list, MCP config (or `None`), prompt file, model, budget, and the exact tools and MCP servers its init event must list. `DIGEST_LOCKDOWN` is the digest's (it also denies `mail_accounts` and `mail_search`, which the runner runs itself); `DISALLOWED_TOOLS` is the shared deny list, for other runs to reuse.
- `build_command(claude_exe, output_schema, edit_paths, lockdown=DIGEST_LOCKDOWN)`: the lockdown argv. `edit_paths` become one exact `Edit(/<path>)` rule each (`edit_rules`); nothing else is editable. Every built-in tool but Edit is allowed outright. An empty `tools` gives `--tools ""` (no built-in tools), and `--allowedTools`, `--disallowedTools` and `--mcp-config` are left out when empty or `None`.
- `build_context(now, targets, mail, urgent)`: the run-context user message (time, KB paths, a note if `inbox.md` is missing, the runner's due and overdue picks, then each searched account's messages from `mailbox.gather_mail`, one JSON line each, and each account that wasn't searched). Nothing in it comes from the model; only the message fields come from email, already wrapped in `<untrusted_email_content>` by the mail tool. `target_lines(now, targets)` is its time, week and KB-path lines, which the checker's writer context reuses.
- `compose_prompt(routine, tag, out_path)` (`prompt.py`): writes the routine, then the shared line rules and KB conventions (`refdocs/routines/kb-line-rules.md`, `{tag}` filled in), to `out_path`, the system prompt file of a run that edits `life/`. Both runners call it just before claude starts.
- `output_schema(aliases)`: the `--json-schema` string: `suspicious` and `summary` only (the runner works out the completed accounts and the announcements itself). `closed_object(**properties)` and `array_of(**properties)` are its schema helpers, for other runs' schemas.
- `find_claude()`: `claude.exe` on PATH, else the newest VS Code extension's bundled binary. Raises `ClaudeNotFoundError`.
- `run_claude(argv, stdin_text, LaunchOptions(cwd, timeout_s, stderr_path, lockdown=DIGEST_LOCKDOWN))` returns a `ClaudeRun(result, error, version)`.
  - Output is stream-json. `read_events(lines, kill, cwd, lockdown)` checks the `init` event with `init_problems(event, cwd, lockdown)` (permission mode `dontAsk`; tools exactly the lockdown's `expected_tools`, all strings, for the digest Read, Edit, StructuredOutput, `mail_read` and `mail_thread`; MCP servers exactly its `expected_mcp_servers`, for the digest `mail: connected`; cwd is `cwd`; `additional_directories` empty if present) and kills claude on any mismatch, or if a result arrives without an init.
  - A timer kills it after `timeout_s`, and a claude still running once its output ends is killed. Every kill (these two and the init check's) takes its whole process tree, MCP servers included, so none can hold its output open or outlive it. stderr goes to a file, overwritten each run.
- `parse_result(run, aliases)` returns a `RunResult`. It never raises. It keeps `suspicious` entries only with a known alias, a hex Gmail id and a bare sender address, at most 20. Dropped entries are counted in `dropped`.
  - `structured_output(run)` is `(output, "")` on a normal finish, else `(None, why)`; `run_cost(run)` is its cost. The checker parses its own outputs with these.
  - `slugify(text)` and `clean_sentence(text)` (`fields.py`) make keys and speakable sentences.
  - `clean_sentence` (used for every spoken due or overdue item, whose text may come from email) reads only up to 480 chars, has URLs and markup stripped, loses every sentence with a domain, an `@` or a 6+ digit number (spaces ignored), and is cut at a word break to about 120 chars. An item with nothing left is dropped by its caller.

## Files

`lockdown.py`, `command.py`, `init_check.py`, `launcher.py`, `prompt.py`, `schema.py`, `result.py`, `fields.py` (single-field validators), `context.py`.

## Dependencies

`mail_digest.settings`, `mail_digest.child_env`, `mail_digest.announce` (the `Announcement` type), `mail_digest.kb` and `mail_digest.mailbox` (types for the context). Standard library only.
