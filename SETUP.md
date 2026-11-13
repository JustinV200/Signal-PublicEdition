# Setting up Signal

## Before you start

- [uv](https://docs.astral.sh/uv/) (it brings Python 3.12) and the [Claude Code CLI](https://docs.anthropic.com/en/docs/claude-code). Everything else is per tool:
- Microsoft Edge for the browser, mail sign-in and the console; Node.js (LTS) for the console's web front end; Docker Desktop only for the optional container browser.
- A Google Cloud project for Gmail and Calendar (setup walks you through it, about 15 minutes).

`setup prereqs` (or the first screen of setup) lists what's missing, with download links.

## Running setup

```
.\setup.ps1          # Windows: the setup window (the wizard in the Signal console)
.\setup.ps1 --no-ui  # Windows: the same setup in the terminal
.\setup.ps1 mail     # just one tool, in the terminal (set up or redo)
./setup.sh           # Linux (the terminal setup; the window is Windows-only)
```

Or in Claude Code: `/setup`, "set up", "set up the whiteboard", "remove jobhunt". `/setup` opens the same window; say "in chat" (or `/setup --no-ui`) to do it in the conversation instead. The `setup` skill runs the same commands and only steps in when something fails.

### The setup window

`setup` first installs and builds the console (its own registry steps, so they count as progress), then opens it on the Setup tab. The wizard runs the same setup CLI behind each button, so the window and the terminal share one progress file:

- A welcome with the intro and any missing programs, then a checklist of every tool with its platform. Each tool, and each optional step, can be skipped.
- One screen per picked tool: its steps with a status word and mark (`✓ done`, `– skipped`, `✗ failed`, `○ to do`) and a button each (Run, Yes/No, Mark done, a value to save, a settings form, or the copytone samples panel). Output shows live. If a step fails, **Hand to Claude** sends the error to your session in the Chat tab (or copies it when no session has claimed the console).
- Steps that take a password or Windows Hello get **Open a terminal**, which runs `setup.ps1 <tool>` in a new window; the wizard never takes secrets.
- Settings forms are built from each tool's settings schema; placeholders are flagged until you replace them.
- Permissions shows the full summary before **Write this**; then a summary of each tool's health, and an optional tour of the console's views and of GUIDE.md.

Close it any time: it reopens at the first unfinished tool. The console's Tools tab shows each tool as Active, Down or Not set up later on, with a button that opens the wizard at that tool.

Setup goes in this order:

1. A short intro and a check for missing programs.
2. A checklist of tools with their platform. Pick the ones you want; the rest are skipped and get nothing.
3. Each tool's steps: install, config, sign-ins, settings. Optional steps say their default; press Enter to take it or `s` to skip.
4. One summary of what it will add to Claude Code (MCP servers, permission rules, hooks). You confirm once.
5. A check of every tool you picked, then an optional tour.

Progress is saved after every step in `.setup/progress.json`. Ctrl+C and running setup again picks up where it stopped. `setup status` shows each tool's state.

## Settings and placeholders

Tools with settings get a settings step. It creates the tool's config from its `*.example.*` file, asks the basic settings (Enter keeps the value shown), then offers the advanced ones.

The examples ship placeholder values that can't work as they are: `example.edu` and `example.com` hosts, `YOUR_...` names, `<...>` slots and `TODO(owner)` lines. Setup asks for each one with a hint of what to enter, won't take another placeholder as an answer, and doesn't count the tool as set up while any is left. `setup status` and `setup verify` list the ones left.

Signal's own rules have one setting too: `setup config agents` sets when an agent hands off to a fresh one (the percent of its context window in AGENTS.md section 4; 30 to 90, default 75). Lower hands off sooner, so agents work with a fresher context but hand off more often.

Change settings any time:

```
setup config                 # every chosen tool, interactively
setup config whiteboard      # one tool
setup config jobhunt --list  # as JSON
setup config mail-digest --set RunTimes=07:00,18:00
```

(Run these as `.\setup.ps1 config ...`, or ask Claude to "change the digest time".) A change that affects a scheduled task re-registers it.

## What setup writes

- Each tool's config, copied from its example and filled in with your values (gitignored), or a tracked file such as a `schedule.psd1`.
- `.mcp.json` with the servers of the tools you picked, and `.claude/settings.local.json` with their permission rules and hooks. Your own entries in both are kept. It never sets a permission mode.
- `.env` (from `.env.example`) for non-secret values such as a Spotify client ID.
- Your email address in the mail tool's `SELF_ADDRESS` and the calendar's `OWNER_EMAIL`. These are source constants on purpose: the digest only ever goes to that address, and nothing at runtime can change it.
- Optionally, usage in Claude Code's status line (`~/.claude/settings.json`), only if you have no status line already.

## Browser approvals

Setup asks whether Claude may use the browser without asking before every click. Either way, the browser's own gates stay on: purchases, sends and deletes always wait for your approval in a dialog on your PC, and Duo prompts are yours alone.

## Secrets

Never type a password, token, code or client secret into the chat. Steps that need one run in your own terminal; Claude tells you the command. Logins go into the vault (`uv run --project tools/vault vault add ...`), which unlocks with Windows Hello, and the browser fills them without the model seeing them.

## Removing a tool

`setup choose` with the tool left out, then `setup wire --yes`, or tell Claude "remove <tool>". Its MCP server, permission rules and hooks are taken out; its local files stay until you delete them. To remove a scheduled task, run the tool's `unregister.ps1` (or `install-schedule.ps1 -Uninstall` for jobhunt).

## Linux

Only usage tracking and copytone are listed for Linux, and neither is tested there. Scheduled-task steps are skipped. Use `./setup.sh`.
