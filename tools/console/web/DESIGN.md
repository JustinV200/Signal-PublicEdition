# Signal console: design spec

Build contract for `tools/console/web`, a front end to the Claude Code orchestrator: typed messages go to Claude, buttons run directly in the console server, and otherwise the UI only reads status.

## 1. Concept

A radar HUD. The console opens on a scope: a dark face with range rings, a crosshair grid, a slow sweep and labelled blips for Claude, the voice hub, the board and any request still in flight. Chat, Voice and Boards sit behind tabs beside it, a status line above, an input line below. One monospace face, one phosphor hue (cyan) for accent and glow, rules for chrome, motion that only confirms something happened. The glow stays restrained and the sweep slow and low-contrast: readability first. Usability beats the look: everything clickable is a bordered button or tab with a plain verb label, anything inert is plain text with no hover, and a button that cannot work is disabled with its reason beside it.

**Colourblind rule (the owner is red-green colourblind).** Colour never carries meaning alone: every state also has a label, shape, weight or position (`Running`/`Stopped` text plus filled/hollow dot, the word `failed`, `you` bold vs `claude` regular, `▸` on the selected row, the active tab filled and bold, `Showing` in bold on the board that is up, blips as disc / ring / square / diamond with a text label). There is no red-versus-green signal anywhere: the palette is one cyan phosphor, amber for warnings and pink for failures, which stay apart under deutan and protan vision.

## 2. Layout

Three rows: status line (fixed: a 36px title row, then the tab row), view (scrolls), input line (1 to 8 text rows, fixed). Text sits in one centred column, `max-width: 96ch`, 24px side gutters; rules span the full window.

- Laptop (1366-1536px): 14px type, column about 800px.
- 4K (≥2200 CSS px): 16px type, column about 920px. Nothing else widens; prose past 100ch reads worse.
- Narrow (<720px): gutter collapses to a line above the body; tabs drop their status words and hints; the app name is hidden.

Views `scope` (default and home), `chat`, `voice`, `boards`, `tasks`, `devices`, `models`, `tools`, `setup`: a tab click or `Ctrl+1` to `Ctrl+9` swaps the body; the input line stays in every view, and sending a message switches to `chat`, where the reply lands.

```
 Signal console   Connected to Claude · working 0:42                            [? Help]
 [Scope Ctrl+1] [Chat Ctrl+2] [Voice ● listening Ctrl+3] [Boards showing your board Ctrl+4]
 ───────────────────────────────────────────────────────────────────────────────
  14:02  you     load the lecture board and tell me what's due this week
  14:02  action  Load whiteboard board 'lecture' · done
  14:03  claude  Loaded. Due this week:
                 - HIST 205 problem set 4 (Thu)
                 - Club demo notes, see `life/areas/club/`
  14:05  claude  Background: the Spotify search fix passed review and is pushed.
  14:06  you     ok, and push the handoff doc
  14:06  claude  working 0:42
                                                                       ↓ 1 new
 ───────────────────────────────────────────────────────────────────────────────
  ›  Message Claude…                                   [Commands Ctrl+K] [Send Enter]
```

Scope view: `SCOPE   Live state at a glance…`, then the radar (up to 400px) beside a readout `CLAUDE  working 0:42 (main session)` / `VOICE HUB  running · listening` / `BOARD  your board` / `PENDING  Load whiteboard board 'x'`. Voice view: header `VOICE   ● Running · listening   started by console   [Start voice] already running  [Stop voice]`, a hint line, then the feed. Boards view: header `Boards   On the projector now: the to-do list`, a hint line, then a bordered list of rows like `▸ To-do list   Showing` / `  lecture   saved 2h ago` beside a preview panel of the selected row with the one `[Send to projector]` button.

## 3. Typography

IBM Plex Mono from `@fontsource/ibm-plex-mono` (400, 400 italic, 600); fallback `"Cascadia Mono", Consolas, ui-monospace, monospace`; `tabular-nums` everywhere.

| Use                                           | Size              | Weight          | Line height |
| --------------------------------------------- | ----------------- | --------------- | ----------- |
| Body, input, feed                             | 14px (16px at 4K) | 400             | 1.55        |
| Status line, timestamps, gutter labels, hints | 13px              | 400 (`you` 600) | 1           |
| Markdown h1 / h2 / h3+                        | 16 / 15 / 14px    | 600             | 1.4         |
| Code block                                    | 13px              | 400             | 1.5         |

## 4. Colour tokens

Dark always, whatever the OS says: a near-black scope with a teal cast. Light is included as an opt-in (`theme light` in command mode sets `data-theme="light"` on `<html>` and remembers it in `localStorage`) and drops the glow.

| Token         | Role                                                                                             | Dark                    | Light                  |
| ------------- | ------------------------------------------------------------------------------------------------ | ----------------------- | ---------------------- |
| `--bg`        | window                                                                                           | `#070b0d`               | `#f4f7f6`              |
| `--bg-2`      | status line, input area, panels, code blocks                                                     | `#0b1214`               | `#e9efee`              |
| `--bg-3`      | hover and selected rows, active tab, inline code                                                 | `#122022`               | `#d9e4e2`              |
| `--fg`        | text                                                                                             | `#d3e6e4`               | `#15201f`              |
| `--fg-2`      | muted: `claude` label, action text, meta                                                         | `#8ea8a5`               | `#4e6462`              |
| `--fg-3`      | faint: placeholders, hints, captions                                                             | `#56716e`               | `#7d918f`              |
| `--rule`      | 1px lines                                                                                        | `#173230`               | `#c9d8d5`              |
| `--accent`    | the phosphor: HUD labels, links, focus ring, `▸`, primary buttons, the whole scope               | `#62e4da`               | `#0a8f86`              |
| `--ok`        | running dot (same phosphor)                                                                      | `#62e4da`               | `#0a8f86`              |
| `--warn`      | offline, no orchestrator                                                                         | `#e5b04a`               | `#9a6600`              |
| `--error`     | failed                                                                                           | `#ee8fc0`               | `#b8407a`              |
| `--selection` | text selection                                                                                   | `#15433f`               | `#bfe5e1`              |
| `--glow`      | `text-shadow` / `box-shadow` colour behind HUD labels, active tab, hovered primary button, blips | `rgba(98,228,218,.45)`  | transparent            |
| `--grid`      | the HUD grid lines behind the views, every 48px                                                  | `rgba(98,228,218,.045)` | `rgba(10,143,134,.06)` |

**HUD labels** (`.hud-label`): view titles, readout keys and the app name are 13px, uppercase, 600, letter-spaced 0.1em, in `--accent` with a 6px glow. Body text never glows.

## 5. Components

**Scope** (`views/scope`). One SVG, viewBox 400, drawn entirely in `--accent` at low alpha: a face filled at 5% with a 45% rim, three range rings and a crosshair plus 30° ticks at 22%, and a sweep (a leading radius at 45% with an eight-step trail fading from 16% to 0) turning once every 8 s, linear. Blips: Claude at the centre (disc when a session is claimed, ring when not; label `CLAUDE · <turn words>|no session`, the status line's words below; a ring with a slow pulse, `anim-pulse-slow`, while only its agents run), the voice hub at bearing 330° on the middle ring (disc running, ring stopped; `VOICE · listening|thinking|speaking|stopped`), the board at 120° (square; `BOARD · the to-do list|your board|nothing`, the words of `board.view`), and up to four pending requests on the outer ring from 150° every 45° (diamonds; the action text, cut at 24 chars; the same pending rows as the buttons, so only requests this page sent, until done, failed or two minutes old). A blip whose thing is in flight (Claude busy, a pending request) pulses with `anim-pulse`. Labels are 12px `--fg`, anchored away from the centre so they never leave the viewBox. The readout beside it repeats every fact as text, so the picture is never the only copy. The sweep and pulses stop when the document is hidden (`usePageVisible`) and under reduced motion.

**Stream.** A message is a row: gutter `HH:MM  role` (13px, 14ch, `fg-2`) then the body. `you`: label 600 in `fg`. `claude`: label `fg-2`, body markdown, unprompted replies included. `action`: label `action`, body `fg-2`. `note` (a console notice from the `note` event, e.g. the orchestrator claim changed): label `note` 600 in `--warn`, body 600 in `fg`, so the label text, weight and colour each mark it. A `fg-3` centred divider marks a day change. Delivery: _sending_ body at 60% opacity; _sent_ full; _failed_ adds `failed: <error>` in `--error` under the body with a Retry button (re-sends as a new message). An `action` row ends with where its run has got to, in `fg-3` after `·`: `sending…`, `working…` (the server is running it) or `done: <what happened>` (`sent` only on replayed rows from before buttons ran in the server); a failed run gets the `failed: <error>` line. `state/actions/actionProgress.ts` derives it from the row's `delivery` (`running`, `done` with `result`, `failed` with `error`), and the same derivation keeps the button that sent it in its pending state and plots the scope's pending blips (only rows with a local origin, so a replayed row never pends; capped at two minutes so a lost result cannot wedge it).

**Working indicator.** `orchestrator.turn` comes from the orchestrator's turn hooks (a sent request reads `sent` until its turn starts). While its `state` is `working`: a last row `claude  working 0:42` ticking `m:ss` since the turn's `startedAt`, and the segment reads `Connected to Claude · working 0:42` (` · 5 agents` added while subagents run). The other states read `waiting on 5 agents`, `no word from Claude for 12 min (interrupted?)` (stale, also in `--warn`), `status unknown until Claude's next turn`, and nothing extra for idle; a `?` after the agent count means the two sources disagree and the lower is shown. `status/turnWords.ts` holds the wording. The clock is the signal; no spinner.

**Input line.** Textarea (placeholder `Message Claude…`) behind a `›` glyph (`fg-3`, `accent` when focused), caret in accent, grows 1 to 8 rows then scrolls, followed by a `Commands` button (hint `Ctrl+K`) and a primary `Send` button (hint `Enter`; disabled with `type a message first` while the draft is empty). Enter sends, Shift+Enter newline. Up on an empty or unedited draft recalls sent messages (last 50, `sessionStorage`), Down goes forward, typing leaves recall. _Confirm mode_ (reached only from the palette's voice commands) replaces the textarea with `stop the voice hub? [y/n]`: `y` sends, `n` or Esc cancels. _Command mode_ (`Ctrl+K` or Commands): glyph becomes `:`, up to 8 clickable matches rise above the line: `voice start`, `voice stop`, `board load <name>` per save, `board todo` and `board idle` (left out only when the whiteboard is on but reports no view), `board realign` and `board calibrate` (via confirm; both left out under the night view), `view scope|chat|voice|boards|tasks|devices|models`, `theme dark|light`. Substring filter, Up/Down, Enter runs (voice via confirm), Esc closes.

**Voice.** Tab: dot plus phase text, filled when running, hollow when stopped; text `listening` / `thinking` / `speaking` / `stopped`. View header: `Running · <phase>` or `Stopped`, `started by console|external`, then `Start voice` and `Stop voice` buttons that run at once (no confirm): the one that does not apply is disabled with `already running` / `not running` beside it, and a clicked one reads `Working…` until the console has run it. A `fg-3` hint line under the header says the buttons run at once in the console and the result shows in Chat. Feed rows `HH:MM:SS  kind  text`, kind column 6ch: `heard` quoted, `said` plain, `note` in `fg-3`. Newest at the bottom, auto-follow.

**Boards.** Header `Boards   On the projector now: <the to-do list|the idle board|your board|nothing>` (the words of `board.view`, which is `todo`, `idle` or `items`; the whiteboard never says which save is loaded) and a `fg-3` hint (`Click a board to preview it, then send it to the projector. The console loads it at once…`). Then two columns (stacked under 720px): a bordered list of rows with roving focus (the to-do list, then the idle board, then the saves), the selected row showing `▸` and `--bg-3`; columns name, `saved <relative>` (`fg-2`, blank for the to-do list and idle board) and `Showing` in 600 on the to-do row while `board.view` is `todo`, or on the idle row while it is `idle` (no save row can match). A click, focus or Up/Down (on the list or from the input line) only selects, and focus follows the cursor; nothing loads from a row. Beside it, a preview panel (`--bg-2`, 1px `--rule`) shows the selected row's name, `on the projector now` when it is up, its description (`board.saves[].description`, else `No description saved.`), `saved <relative>`, and the one primary `Send to projector` button, captioned `Puts this board on the projector now, replacing what is showing.` The button reads `Working…` while a load runs (repeat clicks are ignored) and is disabled with `Not available yet: the whiteboard needs an update` for the to-do list and idle board only when the whiteboard is on (`board.online`) but `board.view` is null (an older whiteboard build). When the whiteboard is off (`board.online` false: no saves, no view) every button stays on, because a board command starts it (the whiteboard CLI does), and a `fg-2` note under the hint says so. The echo lands in chat as an action row. Empty list with the whiteboard on: `No saved boards yet.` The preview is text only until the whiteboard serves thumbnails.

**Boards header buttons.** Beside `On the projector now:`, `Realign board` (action `board.realign`, no confirm: a one-second marker flash that keeps the items) and `Full calibrate` (action `board.calibrate`, through the confirm line: `Flash calibration markers on the projector? [y/n]`). Both are disabled with `Night view is on; calibration would light the room` while `board.view` is `night`. The preview panel adds `Update` (action `board.update`) for a save with a `refresher` and for the to-do list, captioned `Update redraws it from the live tasks or plans, not the old save.` What happened (or why it failed) is on the action's row in chat.

**Models** (`models`, `Ctrl+7`). Its own view, so the pickers are not on every page: header `MODELS`, a `fg-3` hint, then the model strip's two 13px rows. `ORCHESTRATOR  now: opus-5-5 · medium  next session [model ▾] [effort ▾]  applies to every new Signal session, not this one`, then `VOICE  [model ▾] [effort ▾]  applies on your next request`, then a `fg-3` hint that the running session switches from the model name under the VS Code prompt box. Unknowns read `model unknown` / `effort unknown`. The pickers are native selects styled like buttons (bordered, dashed and faint when disabled, with the reason as tooltip); options are words (`use my user settings`, `sonnet`, `high`), and a value off the list shows as a disabled placeholder (`audiohub.toml default`, `other: X`). Like the Away/Here toggle, a pick acts directly; a refused write shows its error under the strip in `--warn`.

**Tasks** (`views/tasks`, `Ctrl+5`). Data from the `tasks` SSE event, a full snapshot like `state`. Header `TASKS   4 active · 1 needs you · overall 58%`, and on the right in 13px `5h 42% (resets 14:10) · wk 18% · agents 5 · as of 2m ago` (a window that is null or past its reset reads `5h --`). Rows in the server's order (most finished first): `[1 review]  Brief phase 2  60%`, the tag 14ch wide; a `needs_you` row adds `YOU: <text>` in 600; then `next: <text>` in `fg-2`. Then `Queued: 6 tasks, none started` and `Done today: 3`, each with its names in `fg-2`. Done shows 6 names; with more, a `Show all N done` / `Show fewer` Button (`aria-expanded`) follows, the choice kept in `sessionStorage` (`signal-console-tasks-done-open`), collapsed by default. The tag is the board's number plus the word; its colour (`accent` for review, `warn` 600 for needs you) is only a second cue. Empty: `No tasks reported. The orchestrator writes them with console tasks set.` The tab reads `3 active · 1 needs you`.

**Devices** (`views/devices`, `Ctrl+6`). Polls `GET /api/devices` every 5 s while open and visible; the header says `checked 5s ago` or `Not updating: <why>`. A `--bg-2` block `YOU  Here | Away until Thu 17:00 | Asleep (sleep mode)` with `I'm away` (and an optional until field: a weekday, `tomorrow` or a date) or `I'm back`; this toggle calls `POST /api/away` directly, the owner's own switch, and reads `Saving…` while it runs. Then a bordered list, one row per device: a shape (`●` on, `○` off, `?` unknown), the name (22ch), the state word in 600 and the server's words (`Projecting your board`, `Live, 1920x1080 via msmf, calibrated`, `Running, listening (started by console)`, `In use by the voice hub`, `Not running`). The webcam row has `Open camera` (disabled with `the camera isn't live`), which opens a `--bg-2` panel below with the live picture, `Camera: live|connecting…|stopped` and `Close camera`; the server's errors (2 viewers already, no picture, whiteboard off) show in `--warn` in words. Closing the panel or leaving the view ends the stream.

**Buttons** (`ui/Button`). Every clickable control that is not a tab or a list row: 26px tall, 1px `--fg-3` border, 3px radius, `--bg-2` fill, a plain verb label, an optional shortcut hint in `fg-3`, `cursor: pointer`. Hover fills `--bg-3` and brightens the border to `--fg-2`, press darkens to `--bg`, focus is the accent ring. _Primary_ (Send, Send to projector) has accent border and text. _Pending_ reads `Working…`, keeps a solid border, `cursor: progress`, ignores clicks. _Disabled_ goes `fg-3` with a dashed `--rule` border and `not-allowed` cursor; the reason is the tooltip and a `fg-3` caption right after the button.

**Status line.** Two rows on `--bg-2`. Title row: `Signal console` in 600, then the connection in words (`Connecting…`, `Connected to Claude`, `Connected to Claude · <turn words>` as in the working indicator, `Not connected · retrying in 3s`, `Not connected`), both inert text in `fg-2`, the claimed session's label only in the tooltip (`Session: <label>`), never beside the app name; at the right `updated 3s ago` (when the server last sent anything, keepalives included; `updated 2m ago` past a minute, `--warn` past 20 s, when the stream is reopened) in `fg-2`, a `Refresh` button (re-reads the state, the tasks and the open view's polls now) and the `? Help` button. Tab row: `Scope Ctrl+1`, `Chat Ctrl+2`, `Voice ● <phase> Ctrl+3`, `Boards showing <the to-do list|your board|the night view> Ctrl+4` (`nothing showing` while `board.view` is null), `Tasks <3 active · 1 needs you|none active> Ctrl+5`, `Devices Ctrl+6`, `Models Ctrl+7`, left-aligned 26px bordered boxes; the active one filled `--bg-3`, border `--fg-2`, name in 600.

**Tools** (`views/tools`, `Ctrl+8`). Header `TOOLS  2 active · 1 down · 11 not set up  [Check again] [Open setup]`, then one row per registry tool: a mark and a bold word (`● Active`, `✗ Down`, `○ Not set up`), the name, what the check said, the platform, and a button (`Set up`, `Continue setup`, `Fix`, `Re-run setup`) that opens the wizard at that tool. From `setup status --json`.

**Setup** (`views/setup`, `Ctrl+9`). Header `SETUP  step 3 of 9`, a hint, a strip of numbered screen buttons (current one `▸` and bold, finished tools `✓`), the screen, then Back / Next. A step row reads `✓ done | – skipped | ✗ failed | ○ to do`, its title and `optional`/`required`, then its controls; a command's live output shows in a `--bg-2` block under a result line (`✓ done`, `✗ failed`, `! needs you`), with **Hand to Claude** on a failure. Placeholders read `! placeholder: replace it`. The console tour is a bar above the view (`TOUR 2/9 · Chat`, Back / Next / End tour) with an accent left rule, switching the view at each stop.

**Help.** `? Help` (reads `Close help` while open) toggles a panel at the top of the view: what Scope, Chat, Voice and Boards do, that typed messages go to Claude while buttons run at once in the console, and the shortcuts. Esc or its Close button closes it.

**Empty chat:** three `fg-3` lines: `Connected to <label>.`, how to send, where Voice, Boards and Help are.
**Offline** (SSE closed or `/api/state` failing): the connection words read `Not connected · retrying in 3s` in `--warn`; input stays usable; backoff 1, 2, 4, 8 s. A stream with no bytes for 20 s is reopened the same way, and the page resyncs (fresh `/api/state`, stream reopened) when it becomes visible again or the network returns.
**No orchestrator** (`claimed` false): `Not connected` in `--warn`, tooltip `No Claude Code session has claimed the console`.
**401:** body replaced by a left-aligned block: `signal console`, `not signed in`, `run  console open  in a terminal to open a signed-in window` (command in inline-code style); no input line. Login retried on `hashchange` and window focus.

## 6. Motion

`--ease-out: cubic-bezier(0.2, 0, 0, 1)` for things that appear, `linear` for colour. Nothing bounces; nothing animates on initial load or SSE replay.

| Trigger                           | Animation                                                                                                                                                                                |
| --------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Message or feed row appended live | opacity 0→1, translateY 4px→0, 160ms ease-out                                                                                                                                            |
| Working row appears / leaves      | opacity 120ms ease-out / 120ms linear                                                                                                                                                    |
| View switch                       | incoming opacity 0→1 + translateY 3px→0, 140ms ease-out; outgoing removed instantly                                                                                                      |
| Tab status text changes           | new text opacity 0→1, 120ms (span keyed by value)                                                                                                                                        |
| Help panel opens                  | opacity 0→1, 120ms ease-out; close instant                                                                                                                                               |
| Scope sweep                       | rotate 360° every 8s, linear, infinite; `animation-play-state` follows page visibility                                                                                                   |
| Blip in flight                    | `anim-pulse` (opacity 1↔0.35, 1200ms)                                                                                                                                                    |
| Phase dot                         | listening: static. thinking: opacity 1↔0.35, 1200ms ease-in-out, infinite alternate. speaking: three 2px bars scaleY 0.3↔1, 900ms ease-in-out, infinite alternate, staggered 0/150/300ms |
| Palette opens                     | opacity 0→1, translateY 4px→0, 120ms ease-out; close instant                                                                                                                             |
| Row, tab and button hover         | background-color and border-color 80ms linear                                                                                                                                            |
| Sending → sent                    | opacity 0.6→1, 120ms linear                                                                                                                                                              |
| `↓ N new` pill                    | opacity 120ms; click scrolls `smooth`; live auto-follow is instant                                                                                                                       |

`prefers-reduced-motion: reduce`: no translates, no infinite animation (the sweep stands still, dots and blips stop pulsing; the words carry the state), opacity fades at 80ms.

## 7. Keyboard and focus

| Keys                           | Action                                                                          |
| ------------------------------ | ------------------------------------------------------------------------------- |
| printable key, nothing focused | focus the input and insert it                                                   |
| Enter / Shift+Enter            | send / newline                                                                  |
| Up / Down on empty draft       | history recall                                                                  |
| Ctrl+K                         | command mode                                                                    |
| Ctrl+1 to 9                    | scope / chat / voice / boards / tasks / devices / models / tools / setup        |
| Esc                            | close help, else the palette or confirm, else back to the scope and focus input |
| PageUp / PageDown / Ctrl+End   | scroll the view from the input; jump to bottom                                  |
| Up / Down in boards            | move `▸` only; the preview's button loads                                       |

`:focus-visible` is a 1px solid `--accent` outline, offset 2px, no glow. The input shows focus by the `›` turning accent and its top rule brightening to `--fg-3`. Focus returns to the input after any action, confirm or view switch. Buttons, tabs and board rows are real `<button>`s with the bordered looks in section 5; nothing clickable is styled as plain text, and nothing inert gets a hover state.

## 8. Rendering Claude's text

`react-markdown` + `remark-gfm`, producing React elements (never `innerHTML`). Raw HTML shows as literal text. `urlTransform` keeps `http:`/`https:` only; other hrefs render as plain text. Links: `<a target="_blank" rel="noopener noreferrer" title={href}>`, accent, underline at 50% alpha, full on hover. Images never fetch: rendered as a link `[image] alt`. Bodies get `overflow-wrap: anywhere`.

| Element              | Look                                                                                  |
| -------------------- | ------------------------------------------------------------------------------------- |
| Paragraph            | body text, 0.6em between blocks                                                       |
| h1 / h2 / h3+        | 600 at 16 / 15 / 14px, 0.9em above, no `#`                                            |
| Bold / italic        | 600 / Plex italic                                                                     |
| Inline code          | `--bg-3`, 0 0.3ch padding, 2px radius                                                 |
| Code block           | `--bg-2`, 1px `--rule` border, 12px padding, 13px, horizontal scroll, no highlighting |
| Lists                | 2ch indent per level, `-` and `1.` markers in `fg-2`, 3 levels                        |
| Task item            | checkbox as text `[ ]` / `[x]` in `fg-2`                                              |
| Blockquote           | 2px left `--rule`, 1.5ch padding, text `fg-2`                                         |
| Table                | plain cells, 0 1ch padding, 1px `--rule` under the header, scroll wrapper             |
| Rule / strikethrough | 1px `--rule` / line-through in `fg-2`                                                 |

## 9. Implementation notes

Vite 8 + React 19 + TypeScript 5.9 on Node 24.20 LTS. Plain CSS: `styles/tokens.css` (variables, both themes), `base.css` (reset, font, rows), `motion.css` (keyframes, reduced motion), one `*.module.css` per component. No Tailwind: a dozen tokens, no utility churn.

Exact pins, checked against the registry 2026-10-19, all Node 24 compatible:

| Package                                                        | Version                | Why                                                              |
| -------------------------------------------------------------- | ---------------------- | ---------------------------------------------------------------- |
| `react`, `react-dom`                                           | 19.3.1                 | the stack                                                        |
| `react-markdown`                                               | 10.1.0                 | markdown to React elements, HTML off                             |
| `remark-gfm`                                                   | 4.0.1                  | tables, strikethrough, task lists                                |
| `@fontsource/ibm-plex-mono`                                    | 5.3.0                  | offline font                                                     |
| dev `vite`, `@vitejs/plugin-react`                             | 8.3.4, 6.1.2           | build                                                            |
| dev `typescript`, `@types/react`, `@types/react-dom`           | 5.9.3, 19.3.0, 19.3.0  | TS 7 is outside `typescript-eslint`'s peer range (<6.1)          |
| dev `vitest`                                                   | 5.0.5                  | tests: reducer, session 401 path, URL filter, boards, progress   |
| dev `eslint`, `typescript-eslint`, `eslint-plugin-react-hooks` | 10.13.0, 8.72.0, 7.1.1 | lint                                                             |
| dev `prettier`                                                 | 3.9.10                 | format                                                           |

No router, state library, icon set or animation library.

Files under `src/`; each folder has `README.md` and `index.ts`, and features import `api`, `state`, `markdown` and `time` only through those:

```
main.tsx
app/          App.tsx (login gate)  Shell.tsx (status + view + input)  SignIn.tsx (401)
api/          types.ts  client.ts (fetch, 401, login)  events.ts (EventSource, backoff, dedupe)  camera/ (MJPEG reader)
state/        store.tsx  reducer.ts  dedupe.ts  boards.ts  theme.ts
state/actions/ sending.ts  actionLabels.ts  actionProgress.ts  usePendingActions.ts
status/       StatusLine.tsx  Tab.tsx  PhaseDot.tsx
ui/           Button.tsx  usePageVisible.ts
help/         HelpPanel.tsx
views/scope/  ScopeView.tsx  Scope.tsx  blips.ts
views/chat/   ChatView.tsx  MessageRow.tsx  WorkingRow.tsx  DateDivider.tsx  EmptyChat.tsx
views/voice/  VoiceView.tsx  FeedRow.tsx
views/boards/ BoardsView.tsx  BoardRow.tsx  BoardPreview.tsx
views/tasks/  TasksView.tsx  DoneGroup.tsx  TaskRow.tsx  taskWords.ts
views/devices/ DevicesView.tsx  DeviceRow.tsx  CameraPanel.tsx  AwayControl.tsx  useDevices.ts
views/tools/  ToolsView.tsx
views/setup/  SetupView.tsx  wizardScreens.ts  useStartScreen.ts  useSetupQuery.ts  screens/  steps/  settings/  samples/  run/  health/
input/        InputLine.tsx  useAutoGrow.ts  useHistoryRecall.ts  ConfirmLine.tsx
palette/      Palette.tsx  commands.ts  filter.ts
markdown/     Markdown.tsx  components.tsx  links.ts
keys/         useGlobalKeys.ts
time/         format.ts (HH:MM, HH:MM:SS, relative, m:ss)
styles/       tokens.css  base.css  motion.css
```

Tests in `tools/console/web/tests/`, mirroring `src/`.
