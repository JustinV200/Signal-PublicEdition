# Signal

Signal is a personal assistant system for Claude Code that runs on your own PC, built for Windows with some tools also working on Linux. It gives Claude local tools: a gated web browser, Gmail and Calendar, a daily mail digest, a password vault, a catch-up brief with away mode, background Claude sessions, a task console, spoken notifications and music control, a projector whiteboard, a sleep mode that darkens screens and lights, and a job-application runner, plus rules that have one agent plan the work, hand it to helper agents, and get every result checked by a fresh reviewer. You pick only the tools you want, and setup installs, signs in and checks each one for you.

## Quick start

You need [uv](https://docs.astral.sh/uv/) and [Claude Code](https://docs.anthropic.com/en/docs/claude-code). Then, from the repo root:

```
.\setup.ps1        # Windows
./setup.sh         # Linux
```

On Windows this opens the setup window: a wizard inside the Signal console that runs each step with a button, shows its output live and resumes where you stopped (`--no-ui` keeps the terminal flow; Linux uses the terminal). Or open Claude Code in this folder and say "set up" (or `/setup`), which opens the same window. Every way runs the same setup: pick your tools, then it installs, signs in, asks for each tool's settings, wires Claude Code and checks everything. Stop at any point and run it again to carry on.

## What's in the repo

| Folder | What it holds |
|---|---|
| `tools/` | One standalone project per tool (browser, mail, calendar, mail-digest, vault, brief, sessions, console, audiohub, whiteboard, sleepmode, usage, contextmeter, jobhunt) plus `setup`. Each has its own README. |
| `packages/` | Small shared Python packages the tools build on (untrusted-content frames, JSON state, Google sign-in, and so on). |
| `.claude/skills/` | `setup` (setup and the tour), `copytone` (writes in your own style from your samples), `ponytail` (keeps code small). |
| `refdocs/` | The coding rules, the routines scheduled runs follow, and research notes the code cites. |
| `life/` | Your own notes and plans. Only its README is tracked; everything else stays on your PC. |

## Platforms

Built and used on Windows 11. Usage tracking, the context meter and copytone also run on Linux, untested. Setup shows each tool's platform and skips Windows-only steps (scheduled tasks) elsewhere.

## More

- [SETUP.md](SETUP.md): what setup does, changing settings later, skipping, removing a tool.
- [GUIDE.md](GUIDE.md): how it all fits together and what to say to use each tool (also `setup tour`).
- [AGENTS.md](AGENTS.md): the rules every agent working in this repo follows.

## License

PolyForm Noncommercial License 1.0.0: free for personal and individual use; see [LICENSE](LICENSE). Commercial use needs a separate license, so contact the owner through GitHub (see [COMMERCIAL.md](COMMERCIAL.md)). Some dependencies carry their own licences, such as sleepmode's `openrgb-python` (GPL-3.0), which is installed from PyPI and not bundled.
