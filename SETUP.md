# Setting up Signal

## Before you start

- [uv](https://docs.astral.sh/uv/) (it brings Python 3.12) and the [Claude Code CLI](https://docs.anthropic.com/en/docs/claude-code). Everything else is per tool:
- Microsoft Edge for the browser, mail sign-in and the console; Node.js (LTS) for the console's web front end; Docker Desktop only for the optional container browser.
- A Google Cloud project for Gmail and Calendar (setup walks you through it, about 15 minutes).

`setup prereqs` (or the first screen of setup) lists what's missing, with download links.

## Running setup

```
.\setup.cmd          # Windows: the setup window (the wizard in the Signal console)
.\setup.cmd --no-ui  # Windows: the same setup in the terminal
.\setup.cmd mail     # just one tool, in the terminal (set up or redo)
./setup.sh           # Linux (the terminal setup; the window is Windows-only)
```

On Windows you can also double-click `setup.cmd`. It runs `setup.ps1` past PowerShell's script policy, which blocks scripts on a new PC, so type the `.cmd` (a bare `.\setup` would pick the blocked `.ps1`).

Or in Claude Code: `/setup`, "set up", "set up the whiteboard", "remove jobhunt". `/setup` opens the same window; say "in chat" (or `/setup --no-ui`) to do it in the conversation instead. The `setup` skill runs the same commands and only steps in when something fails.

### The setup window

`setup` first installs and builds the console (its own registry steps, so they count as progress), then opens it on the Setup tab. The wizard runs the same setup CLI behind each button, so the window and the terminal share one progress file:

- A welcome with the intro and any missing programs, then a checklist of every tool in four groups (Core, Everyday, Hardware, Extras) with its platform and what it costs to set up (`15 min, Google account`), plus **Pick all** and **None**. A tool that builds on one you didn't pick offers to add it (**Add Gmail too**). Each tool, and each optional step, can be skipped.
- **Save picks and install** saves the picks and runs every pick's automatic steps (its required installs that need nobody) in one log, then names, per tool, the step it stopped at because it needs you. Optional steps (scheduled tasks, the Docker image) and browser sign-ins always wait for your own click. Each tool's screen has **Run the automatic steps** too.
- One screen per picked tool: its steps with a status word and mark (`✓ done`, `– skipped`, `✗ failed`, `○ to do`) and a button each (Run, Yes/No, Mark done, a value to save, a settings form, or the copytone samples panel). Output shows live. If a step fails, **Hand to Claude** sends the error to your session in the Chat tab (or copies it when no session has claimed the console).
- Steps that take a password or Windows Hello get **Open a terminal**, which runs `setup.ps1 step <tool> <step>` (just that step) in a new window; the wizard never takes secrets. **Check again**, or coming back to the window, shows the result.
- One step runs at a time: the button you clicked reads `Working…` and the others wait.
- Settings forms are built from each tool's settings schema; placeholders are flagged until you replace them.
- Permissions says in one plain line per tool what Claude may do without asking (the exact entries are under **Show exact entries**) before **Add to Claude Code**; then a summary of each tool's health, and an optional tour of the console's views and of GUIDE.md.

Close it any time: it reopens at the first unfinished tool. The Tools list in the console's System tab shows each tool as Active, Down or Not set up later on, with a button that opens the wizard at that tool.

Setup goes in this order:

1. A short intro and a check for missing programs.
2. A checklist of tools with their platform. Pick the ones you want; setup adds nothing for the rest. A tool you set up by hand reads `done; found already set up`. Picked or not, the entries you made for it in Claude Code stay as they are.
3. Each tool's steps: install, config, sign-ins, settings. Required installs just run; other steps ask first. Optional steps say their default; press Enter to take it or `s` to skip.
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
setup config jobhunt --list  # as JSON (incl. `Tailor resume`, Windows only)
setup config mail-digest --set RunTimes=07:00,18:00
```

(Run these as `.\setup.cmd config ...`, or ask Claude to "change the digest time".) A change that affects a scheduled task re-registers it.

## What setup writes

- Each tool's config, copied from its example and filled in with your values (gitignored), or a tracked file such as a `schedule.psd1`.
- `.mcp.json` with the servers of the tools you picked, and `.claude/settings.local.json` with their permission rules and hooks. Your own entries in both are kept: setup lists what it added in `.setup/ledger.json` and only ever takes out or replaces those. It never sets a permission mode.
- `.env` (from `.env.example`) for non-secret values such as a Spotify client ID.
- Your email address in the mail tool's `SELF_ADDRESS` and the calendar's `OWNER_EMAIL`. These are source constants on purpose: the digest only ever goes to that address, and nothing at runtime can change it.
- Optionally, usage in Claude Code's status line (`~/.claude/settings.json`), only if you have no status line already.

## Browser approvals

Setup asks whether Claude may use the browser without asking before every click. Either way, the browser's own gates stay on: purchases, sends and deletes always wait for your approval in a dialog on your PC, and Duo prompts are yours alone.

## Secrets

Never type a password, token, code or client secret into the chat. Steps that need one run in your own terminal; Claude tells you the command. Logins go into the vault (`uv run --project tools/vault vault add ...`), which unlocks with Windows Hello, and the browser fills them without the model seeing them.

## Removing a tool

`setup choose` with the tool left out, then `setup wire --yes`, or tell Claude "remove <tool>". The MCP server, permission rules and hooks setup added for it are taken out; its local files stay until you delete them. Setup can't remove entries you made by hand, so delete those yourself: the tool's server under `mcpServers` in `.mcp.json`, and its rules under `permissions.allow`, its name in `enabledMcpjsonServers` and its hooks under `hooks` in `.claude/settings.local.json`. To remove a scheduled task, run the tool's `unregister.ps1` (or `install-schedule.ps1 -Uninstall` for jobhunt).

## Linux

Only usage tracking, the context meter and copytone are listed for Linux, and none is tested there. Scheduled-task steps are skipped. Use `./setup.sh`.
