---
name: setup
description: Set up Signal or one of its tools (opening the setup window), and give the guided tour. Use when the repo isn't set up yet (no .setup/progress.json), or the user says "setup", "set up", "get started", "first run", "/setup", "setup <tool>", "add <tool>", "remove <tool>", "change <tool> settings", "tour", "how does this work", or "explain <tool>".
argument-hint: [tool id, "tour", "--no-ui", or blank for the full setup]
---

# setup

You run Signal's setup for the user by calling the deterministic `setup` CLI in `tools/setup`. The CLI does every step; you only reason when a step fails. Run every command from the repo root as:

```
uv run --project tools/setup --frozen --quiet setup <command>
```

(Shown below as `setup <command>`.) If `uv` is missing, give the user the install line from `setup.ps1` and stop.

Request: $ARGUMENTS

## Hard rules

- Never ask for or accept a password, token, API key, OAuth code, Duo code or client secret in chat. Steps that need one are marked `"terminal": true` in `setup list`; tell the user to run `.\setup.ps1 <tool>` (Windows) or `./setup.sh <tool>` in their own terminal, then continue when they say it's done. Email addresses, hostnames and folder paths aren't secrets and can be asked in chat.
- Every tool and every optional step is skippable. Never push a tool on the user. A skipped tool gets no config, MCP server, permissions, hooks or scheduled task.
- Never set a permission mode or `bypassPermissions`. Only `setup wire --yes` writes Claude Code settings, and only after the user has seen `setup plan` and said yes once.
- Windows-only tools (`supported_here: false` in `setup list`) can't be set up on Linux: say so and move on.

## The setup window (default)

Unless the request says `--no-ui`, "in chat" or "in the terminal", or asks for the tour or a settings change, open the window first:

```
uv run --project tools/setup --frozen --quiet setup ui [<tool>]
```

It installs and builds the console if needed (long the first time), then opens the console's Setup tab: a wizard that runs these same commands from buttons, shows their output live, and resumes from `.setup/progress.json`. On exit 0, tell the user the setup window is open, that every tool and optional step can be skipped there, and that a failed step has a **Hand to Claude** button that sends the error to you in the console's Chat (fix it as in step 5, then tell them to retry). Then stop; don't run the steps in chat as well. On exit 1 (not Windows, a missing program such as Node.js, or a failed build), say why in one line and carry on with the full setup below in chat.

## Full setup (in chat)

1. Show the intro: the text of `tools/setup/src/signal_setup/data/intro.txt`.
2. `setup prereqs` and tell the user what's missing, with the links it gives.
3. `setup list`. Show the tools as a short checklist: name, one-line description, platform label (`Windows` or `Windows + Linux (untested)`), status. Ask which they want. Mention `needs` (calendar and mail-digest build on mail; mail-digest also on audiohub; jobhunt on browser).
4. `setup choose <id,id,...>` with their picks.
5. For each chosen tool, for each step in order whose status isn't `done`:
   - Optional step: ask (one line, say the default). If they decline, `setup mark <tool> <step> skipped`.
   - `confirm` step (e.g. browser auto-approve, default yes): ask the question as written, then `setup apply <tool> <step> --answer yes|no`. For the browser, say that its own purchase, send and delete confirmations stay on either way.
   - `run`/`copy` step: `setup apply <tool> <step>`. Long installs are normal.
   - `manual` step: relay the text (and open the linked doc if they want details), wait until they say it's done, then `setup mark <tool> <step> done`. For `console.claim`, run the claim command yourself from this session (it must run in the main session).
   - `email` step: ask for the address in chat, then `setup apply <tool> <step> --value <address>`. It writes the address into the mail tool's `SELF_ADDRESS` and the calendar's `OWNER_EMAIL` constants (source constants on purpose, so nothing at runtime can redirect them).
   - `env` step without `terminal`: ask the value, `setup apply ... --value <value>`.
   - `terminal` step: see the hard rules.
   - `samples` step: see "copytone samples" below.
   - `settings` step: `setup apply <tool> <step>` creates the config files from their examples. Then `setup config <tool> --list`; for every `basic` setting and every row with `is_placeholder: true`, ask the user in chat (show the description, hint and current value; they can keep it), then `setup config <tool> --set id=value` (repeat `--set` for several). Offer the `advanced` ones in one question (default no). The step is done only when `placeholders_left` is empty; never invent a value or pass a placeholder (example.edu/example.com hosts, YOUR_..., <...>, TODO(...)). For the mail-digest `checker` step, the hosts are the user's school's LMS and SSO hosts.
   - Exit code 1 means the step failed: read the messages, diagnose (missing program, network, a file the user still has to place), fix what you can without secrets, and retry. Exit code 3 means it needs input or the user's terminal.
6. `setup plan`. Show the summary verbatim and ask once: "Write this?" On yes, `setup wire --yes`; on no, stop (progress is kept).
7. `setup verify` and report each tool as OK or the problem (placeholders left count as a problem: fix them with `setup config`). Tell the user to restart Claude Code or run `/mcp` to load new MCP servers.
8. Offer the tour (default no).

`setup <tool>` from the user: open the window at that tool (`setup ui <tool>`), or in chat do step 5 for that one tool (offering to redo finished steps), then 6 and 7. "Remove <tool>": `setup choose` with the tool left out, then 6. "Change <tool>'s settings": `setup config <tool> --list`, ask, `--set`. The context-handoff threshold in AGENTS.md section 4 is the `agents` tool's setting: `setup config agents --set context-handoff-percent=<30-90>` (lower hands off sooner, with fresher context but more handoffs).

## copytone samples

Goal: 5 to 15 of the user's own writing samples across emails, longer writing and casual messages. Show the running count after each addition (`setup samples count`). Offer, in any combination:
- Files or folders (.docx, .pdf, .txt, .md, code): `setup samples files <path> [<path>...] --kind email|writing|message|code`.
- Pasted text: they paste it in chat; save it to a file in your scratchpad and run `setup samples paste --kind <kind> < <that file>`.
- Their own sent mail (only once the mail tool is done): `setup samples mail`. Show the numbered list (subject plus the first line), let them deselect, then `setup samples keep <n> <n> ...`. Only their own text is kept; quoted replies are cut.

When they're done (or skip), `setup mark copytone samples done` (or `skipped`). Then run the voice test from the copytone skill (`.claude/skills/copytone/SKILL.md`, "Voice test") and `setup mark copytone voice-test done`.

## Tour

`GUIDE.md` is the tour. Give it a section at a time (the `## ` headings), shortest useful version first, and ask whether to go on. For "explain <tool>", give just the matching section, then the tool's own README if they want more. In a terminal, `setup tour [topic]` shows the same thing. The setup window's Tour screen has the same sections plus a walk through the console's own views.
