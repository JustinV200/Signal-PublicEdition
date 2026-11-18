# Signal

Signal is a personal assistant system for Claude Code that runs on your own PC, built for Windows with some tools also working on Linux. It gives Claude local tools: a gated web browser, Gmail and Calendar, a daily mail digest, a password vault, a catch-up brief for when you're away, background Claude sessions, a task console, spoken notifications and music control, a projector whiteboard, a sleep mode that darkens screens and lights, and a job-application runner, plus rules that have one agent plan the work, hand it to helper agents, and get every result checked by a fresh reviewer. You pick only the tools you want, and setup installs, signs in and checks each one for you.

## Quick start

You need [uv](https://docs.astral.sh/uv/), [Claude Code](https://docs.anthropic.com/en/docs/claude-code) and, for the setup window, [Node.js LTS](https://nodejs.org) and Edge. Then, from the repo root:

```
.\setup.cmd        # Windows (or double-click setup.cmd)
./setup.sh         # Linux
```

On Windows this opens the setup window: a wizard inside the Signal console that runs each step with a button, shows its output live and resumes where you stopped (`--no-ui` keeps the terminal flow; Linux uses the terminal). Or open Claude Code in this folder and say "set up" (or `/setup`), which opens the same window. Every way runs the same setup: pick your tools, then it installs, signs in, asks for each tool's settings, wires Claude Code and checks everything. Stop at any point and run it again to carry on.

## The console

The console is a local web page onto your Claude Code session, and it only listens on your own PC. Anything you type goes to Claude as a normal request. The buttons don't go through Claude, they run right away in the console itself. Setup opens it the first time, and after that you open it with `uv run --project tools/console --frozen --no-sync console open` from the repo root, or from the Start menu shortcut if you turned on the console's logon step.

Before it can send anything it has to be linked to a Claude Code session. Chat shows a line to paste into Claude Code that runs `console claim`, and once that's done the page says it's linked. If that session closes, the next session that starts a task takes the link over by itself.

The status line at the top says what Claude is doing, like `Claude · working 0:42`, `Claude · idle` or `Claude session closed`, and shows Away or Asleep when you aren't Here. If one of the console's own checks fails a button shows up there that takes you to System, and `? Help` is always at the right end.

The tabs under it:

- **Scope** is the home view. It's a radar with a blip for Claude, Voice, the projector and each task, with a readout beside it that says the same things in words, starting with anything that needs you. Clicking a blip or a row opens its tab.
- **Chat** is the conversation with Claude. Replies Claude sends on its own land here too, and every button you click gets a row saying how it went.
- **Voice** shows if Voice is running and what it heard and said, with one Start voice / Stop voice button.
- **Boards** lists the to-do list, the idle board and your saved boards with a preview of the one you pick, and Send to projector puts it up. Realign whiteboard and Full calibrate are here too.
- **Tasks** is Claude's task list with each task's progress, anything that needs you first, then what's queued and what got done today. Your Claude usage for the 5-hour window and the week is at the top.
- **System** has the Here/Away toggle, the console's own checks, every tool's status with a button to set it up or fix it, your devices and the webcam view, the model pickers for Claude and Voice, and the dark/light theme.
- **Setup** only shows while a tool you picked isn't finished. It's the setup wizard, one page per tool, and it can hand a failed step to Claude.

The input line at the bottom stays on every tab. Enter sends, Shift+Enter adds a new line and Up brings back what you sent before. Ctrl+K or the Commands button opens Commands, a list of everything the buttons can do that you narrow down by typing (`todo`, `start voice`, `im away`). Full calibrate always asks first, and so does anything that would replace a drawing on the projector. You answer with y or n. Ctrl+1 to Ctrl+6 switch tabs.

`? Help` says what each tab is for, lists the keys and what to check when something's wrong. From there Take the tour walks through the tabs one stop at a time, and it only stops at Voice and Boards if you picked those tools.

Here, Away and Asleep tell Signal if you're around. Set Away in System (or `I'm away` in Commands) and sessions keep working without waiting on you, and the brief keeps what happened for when you're back. Asleep comes from sleep mode and ends when you wake it.

## Tools

Each tool is its own project under `tools/` with its own README, and you only set up the ones you pick.

- [setup](tools/setup/README.md): the first-run setup behind `setup.cmd`, the `/setup` skill and the console's Setup tab. It knows every tool's steps and settings and keeps track of where you stopped.
- [console](tools/console/README.md): the web page described above, plus the `console` CLI that opens it, links it and keeps Claude's task list.
- [browser](tools/browser/README.md): lets Claude drive its own Edge profile, with the safety rules in code. Purchases, sends and deletes wait for your click, and it signs in through the vault so it never sees a password.
- [vault](tools/vault/README.md): a local password vault that fills logins for the browser without any secret reaching Claude. It unlocks with Windows Hello, or a passphrase if you'd rather.
- [mail](tools/mail/README.md): Claude's Gmail tool for your Google accounts. Claude can search, read and draft, and sending a draft waits for you to click Allow.
- [calendar](tools/calendar/README.md): read-only Google Calendar that keeps the next 14 days on hand for the whiteboard's idle board. It signs in through the mail tool's Google project, so set up mail first.
- [mail-digest](tools/mail-digest/README.md): a daily scheduled run that reads your mail and keeps `life/` current with deadlines, overdue work and anything notable, starts each new week's plan and emails you a digest. Urgent things get spoken through Voice.
- [brief](tools/brief/README.md): the catch-up brief. Sessions log what you should hear about, you say "brief me" when you're back, and away mode lets sessions keep going without you.
- [sessions](tools/sessions/README.md): starts and drives headless Claude Code sessions in your other local repos, so this one can hand work off to them.
- [audiohub](tools/audiohub/README.md) (Voice): voice chat with Claude, spoken notifications from every agent, and Spotify control that ducks the music while Claude talks. It's built around Bluetooth audio glasses, or your phone as the mic and speaker, and an NVIDIA GPU is optional for faster speech-to-text.
- [whiteboard](tools/whiteboard/README.md): needs a projector aimed at a real whiteboard and a webcam that can see it. You write with markers, Claude sees it and projects diagrams, text and notes next to your writing, and boards can be saved and sent back up later.
- [sleepmode](tools/sleepmode/README.md): turns the monitors and RGB lights off and puts a night sky on the projector, while the PC stays awake so agents keep working. It wakes at a set time, when you say "good morning" or when you touch the keyboard or mouse. The lights part is optional and needs OpenRGB.
- [usage](tools/usage/README.md): keeps track of your Claude Code 5-hour and weekly usage and how many subagents are running, for the status line, the Tasks tab and the whiteboard.
- [contextmeter](tools/contextmeter/README.md): a hook that tells each agent how much of its context window it has used, so it knows when to hand off.
- [analysis-chamber](tools/analysis-chamber/README.md): takes a question, drafts a plan for you to check, then collects data, analyses it, gets a fresh critic to check the work and leaves a report you can ask follow-up questions about.
- [jobhunt](tools/jobhunt/README.md): an optional job-application runner. A scheduled Claude session applies to a few matching roles per run using only what's in your profile and resume, and logs every field it filled in. Tailoring the resume per posting is optional and needs Microsoft Word.

## What's in the repo

| Folder | What it holds |
|---|---|
| `tools/` | One standalone project per tool, listed under [Tools](#tools). Each has its own README. |
| `packages/` | Small shared Python packages the tools build on: `untrusted` (the frame around outside text), `jsonstate`, `googleauth`, `confirm` (the Allow/Deny dialog), `hubnotify`, `orchestrator`, `tasks`, `brief`, `modelchoice`, `mcpshim`, `displays` and `weather`. |
| `.claude/skills/` | `setup` (setup and the tour), `copytone` (writes in your own style from your samples), `ponytail` (keeps code small). |
| `.claude/agents/` | Read-only subagents the job runner uses to tailor a resume and review it (`resume-tailor`, `resume-reviewer`). |
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
