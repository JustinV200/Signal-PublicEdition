# Signal guide

How Signal fits together and how to use each tool. `setup tour` shows this one section at a time; `setup tour <topic>` shows one.

## The big picture

You talk to one main Claude Code session, the orchestrator. Following [AGENTS.md](AGENTS.md), it plans the work and hands each task to an implementer subagent. A fresh reviewer, with no shared context and a model at least as strong, checks every result against the task and the coding rules before anything is committed. Findings go back to an implementer until the review passes.

The tools give that session hands: a browser, your mail and calendar, a voice, a whiteboard and more. Each tool is a standalone project in `tools/`, installed and wired only if you picked it.

## How tools plug in

- **MCP servers** (browser, mail, brief, sessions, audiohub, whiteboard, sleepmode) give Claude tools it calls by name. Setup lists them in `.mcp.json`.
- **Hooks** run small scripts on Claude Code events: the brief reads new prompts, the console follows turns, usage counts subagents, and the context meter tells each agent how full its context is.
- **Command-line tools and scheduled tasks** (mail digest, calendar cache, jobhunt, the whiteboard's morning run) work without a session open.

## Context meter

After each tool call, every agent and subagent is told how much of its context window it has used, from 40% up, and told firmly to hand off once it passes the AGENTS.md threshold (`setup config agents`). If you run the standard 200k models rather than the 1M ones, set your window with `setup config contextmeter`.

## Task console

A terminal-style window onto your main session, with a Tasks page showing what each agent is doing. Open it with `uv run --project tools/console --frozen --no-sync console open`. The orchestrator reports its tasks there as it spawns, reviews and finishes them. Its Tools tab shows every tool as Active, Down or Not set up, with a button that opens setup at that tool; its Setup tab is the setup wizard, which `setup` and `/setup` open.

## Brief and away mode

Sessions log what you should hear about. Say "brief me" for a ranked catch-up of what happened while you were away. "Away mode on" tells sessions to keep working without waiting for you; each choice they make for you is logged in the brief with how to undo it.

## Voice hub and music

Agents' notifications are spoken aloud in order, so two sessions never talk over each other. Say "play some jazz", "pause the music" or "turn it down". Spotify search and queue need Spotify Premium and a Spotify app (setup walks you through it); without one, play and pause work with any app in the Windows media controls.

## Browser

Claude drives its own Edge profile, only on sites you allow (`setup config browser`). Say "open the course page and find the syllabus". Purchases, sends and deletes always wait for your approval. Logins come from the vault, so no password reaches the model. A throwaway Docker browser is available for jobs you want kept apart.

## Password vault

Holds the logins the browser may fill. Add them in your own terminal: `uv run --project tools/vault vault add github --name GitHub --origin https://github.com`. It unlocks with Windows Hello.

## Mail and calendar

"Any mail from my landlord this week?", "draft a reply saying Thursday works". Claude can search, read and draft; sending needs you to click Allow on your PC. The calendar is read-only: "what's on tomorrow?".

## Mail digest

Every morning (`setup config mail-digest` sets the time) it reads new mail, speaks what matters and emails you a short digest at your own address. `mail-digest --now` runs it on demand. If you keep weekly plans in `life/`, each run also starts the new week for you (the first one too, once `life/inbox.md` exists), carrying over open todos. Give each term's README a `Term dates:` line so it knows when the term ends ([life/README.md](life/README.md#weeks)).

## Assignment checker

On demand, say "check my assignments". It opens your school's Moodle and Google Classroom in a separate, locked-down browser, reads your courses and updates their notes in `life/`. Set it up with the mail digest's optional checker step: your LMS address, SSO host and courses (`setup config mail-digest`), a vault login for the SSO host, then `assignment-check --sign-in-test`. Duo is yours alone: the check waits while you approve on your phone, and nothing ever types a code.

## Background sessions

"Start a session in my website repo to fix the footer" starts a headless Claude Code session there and reports back when it finishes. "What sessions are running?" lists them.

## Whiteboard

A projector and webcam turn a physical whiteboard into one Claude can see and draw on. "Look at the board", "draw a sequence diagram of the login flow", "show my TODO list". Calibrate once with "calibrate the board". When idle it shows the time, weather and news.

## Sleep mode

"Sleep mode" or "good night" darkens every screen, turns RGB lights off (with OpenRGB) and puts a dim night sky on the whiteboard, while the PC and agents keep running. "Good morning", or touching the keyboard or mouse, brings it back. You can give a wake time: "sleep mode until 7".

## Job applications

An optional scheduled run that finds roles matching your profile and applies through the browser, using only facts from your profile and resume. `setup jobhunt` fills in the profile and run settings; `life/areas/job-search/runbook.md` holds the rules it follows. It never solves CAPTCHAs, skips sites that forbid automation, and creates job-site accounts only if your profile says so. Optional, Windows only (needs Microsoft Word): the `Tailor resume` setting has a read-only subagent tailor a copy of your resume to each posting from your resume, websites, GitHub and LinkedIn; a fresh reviewer blocks anything invented, and any failure uploads your base resume.

## Writing in your voice

copytone writes in your own style from your samples (files, pasted text or your sent mail), for emails and posts. Say "test my copytone voice" to check it, or "write this in my voice".

## Safety model

- Web pages, emails and other outside text arrive wrapped as untrusted data; Claude treats them as data, never instructions.
- The browser gates purchases, sends and deletes behind your approval, and its vault keeps passwords away from the model.
- Duo prompts are owner-only: actions on a tab showing one are refused.
- Mail sending needs your click. The digest only goes to your own address, a source constant nothing at runtime can change.
- In away mode, every choice a session makes for you is logged in the brief with its undo.

## Where things live

- Config: each tool's gitignored `*.toml` (copied from its example) and tracked `schedule.psd1` files. `setup config` edits both.
- State: each tool's `.state/` folder (gitignored): sign-ins, logs, caches.
- Your notes: `life/` (gitignored except its README).
- Claude Code wiring: `.mcp.json` and `.claude/settings.local.json`, written by setup.

## Adding or removing a tool

Run `setup <tool>` (or say "set up <tool>") to add one later. Say "remove <tool>" to take its servers, rules and hooks out. A new tool of your own goes in `tools/` as a standalone project, with an entry in `tools/setup/src/signal_setup/data/tools.json` and, if it has settings, a schema in `data/settings/`.
