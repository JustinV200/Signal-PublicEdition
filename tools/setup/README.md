# setup

Signal's first-run setup. Standalone uv project, stdlib only (setup runs before anything else is installed).

- `setup.ps1` / `setup.sh` at the repo root check for uv and run `setup` here.
- `.claude/skills/setup/SKILL.md` drives the same CLI from Claude Code; it only reasons when a step fails.
- The setup window (the Setup tab of `tools/console`) runs the same CLI from buttons through the console server, so the CLI stays the one source of truth for tools, steps, settings and progress.
- `src/signal_setup/data/tools.json` is the tool registry both use: each tool's platforms, prerequisites, steps, MCP servers, permission rules and hooks. Add a tool there, not in code.
- `src/signal_setup/data/intro.txt` is the intro paragraph (first screen and the top of the README; a test keeps them in step).

## Commands

| Command | What it does |
|---|---|
| `setup` / `setup ui [tool]` | The setup window: installs and builds the console with its registry steps if needed, then `console open --view setup` (at one tool when given). Falls back to the terminal setup when it can't (not Windows, a missing program, a failed build), or exits 1 without a terminal to prompt in. |
| `setup --no-ui` | Interactive in the terminal: intro, prerequisites, tool checklist, each tool's steps, one confirmation of the permissions summary, wiring, checks, optional tour. Resumes where it stopped. |
| `setup <tool>` | Set up or redo one tool in the terminal. |
| `setup tour [topic]` | GUIDE.md one section at a time. |
| `setup status [--json]` | Each tool's status, platform label and any placeholders left in its config. `--json` gives each tool's health for the console's Tools page: `active` (done and its verify check passes), `down` (done but the check fails or times out after 8 s) or `not_set_up`; checks run in parallel (`health.py`). |
| `setup intro`, `setup tour --json` | The intro paragraph, and GUIDE.md's sections as JSON, for the setup window. |
| `setup config [tool]` | Change a tool's settings: basic ones first, then any placeholder left, then (if you want) the advanced ones. `--list` prints them as JSON and `--set id=value` (repeatable) sets them without prompting. |
| `setup list`, `prereqs`, `choose`, `apply`, `mark`, `plan`, `wire --yes`, `verify`, `samples`, `config --list/--set` | Non-interactive commands for the setup skill (JSON out; exit 1 failed, 3 needs the user). |

## What it writes

- `.setup/progress.json`: chosen tools and each step's status (gitignored).
- `.mcp.json`: the chosen tools' servers, copied from `.mcp.example.json`, plus any servers you added yourself.
- `.claude/settings.local.json`: the chosen tools' allow rules, `enabledMcpjsonServers` and hooks, merged with your own entries. It never sets a permission mode.
- `~/.claude/settings.json` `statusLine`, only if you accept usage's status line and have no other one.
- `.env` from `.env.example` when missing, and the mail and calendar address constants (`SELF_ADDRESS`, `OWNER_EMAIL`), which stay source constants so nothing at runtime can redirect self-sends.
- copytone samples in `.claude/skills/copytone/samples/` (gitignored).
- Each tool's settings (see below): the gitignored config copied from its example, or a tracked file such as a `schedule.psd1`, edited a line at a time so your comments stay.

## Settings and placeholders

The `agents` entry in the registry is Signal's own rules: its one setting, `context-handoff-percent` (30 to 90, default 75), is the number in AGENTS.md section 4. AGENTS.md is a tracked file whose value sits in prose, so it's marked `<!-- setting:context-handoff-percent -->75<!-- /setting -->` and read by `formats/md_marked.py` (picked by file name; only marked values count).

`src/signal_setup/data/settings/<tool>.json` lists a tool's config files (with the example each is copied from, and a group: "" for the main settings step, `checker` for mail-digest's optional assignment checker) and its settings: key, file, type (`str`, `int`, `float`, `bool`, `list`, `times`), `basic` or `advanced`, description, hint, optional `min`/`max` for numbers, and `rerun` (a step to run again after a change, e.g. re-registering a scheduled task). Defaults are the example files' values.

The examples ship placeholder values (reserved `example.edu`/`.com`/`.org` hosts, `YOUR_...`, `<...>`, `TODO(...)`). A `settings` step is done only when none is left in its files, setup refuses a placeholder as a new value, and `status` and `verify` list any left. A placeholder the schema doesn't name (say a `TODO(owner)` line in the jobhunt profile) is asked for too, with the id `<file>:<key>`.

## Layout

- `settings/`: schemas, the TOML/psd1/Markdown line writers (`formats/`), typed values, the placeholder scan, and the store.
- `registry.py`, `platforms.py`, `progress.py`, `prereqs.py`, `verify.py`, `health.py` (the Tools page's states), `intro.py`, `terminal.py` (prompts)
- `steps/`: runs one step (`settings_step.py` is the settings prompts). `wiring/`: plan, merge and write Claude Code config, plus the small file edits.
- `samples/`: copytone sample import (files, paste, sent mail). `ui/`: checklist, the interactive flow, the tour.
- `cli/`: `main.py` (entry point), `agent.py` (the skill's and the window's commands), `config.py` (`setup config`), `ui_launch.py` (`setup ui`).

## Tests

`uv run --project tools/setup --frozen pytest -q`: wiring only includes finished tools and keeps your own settings, browser auto-approve follows its step, progress resume/skip, the address edit, sent-mail quote stripping, the README intro, the settings line writers, the placeholder scan and gating, that every schema key exists in its example, the AGENTS.md handoff threshold rewrite, tool health states, and the window's terminal fallback.
