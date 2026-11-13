# whiteboard

A projector shines onto a physical whiteboard and a webcam watches it. You write with markers. Claude sees what you wrote and answers by projecting diagrams, text and annotations onto the board, placed next to your sketches.

There are three ways in:

- **Any Claude Code session in this repo** gets the `board_*` MCP tools: look at the board, draw on it, calibrate.
- **The board agent** is a Claude session inside the daemon. It reacts on its own when your ink changes.
- **The `whiteboard` CLI** is for setup and quick checks.

Windows 11, Python 3.12, uv. The board page runs in Edge (already installed). No Node.

## Setup

1. Install: `cd tools/whiteboard && uv sync`.
2. Optional config: copy `whiteboard.example.toml` to `whiteboard.toml` in the same folder and edit it. Every key is optional and the example shows the defaults. `[align] auto = false` turns off automatic re-aligning.
3. Check the hardware:
   - `uv run whiteboard displays` should mark the projector (`PROJ-1 TV`, matched by `[display] name_match`).
   - `uv run whiteboard cameras` should list your webcam. Set `[camera] index` if it isn't 0.
4. Register the MCP server in the repo root's `.mcp.json`, next to `audiohub`. The key must be `whiteboard`:

   ```json
   "whiteboard": {
     "command": "uv",
     "args": ["run", "--project", "tools/whiteboard", "--frozen", "whiteboard", "mcp"]
   }
   ```

5. Keep local state out of git. Add these lines to the repo's `.gitignore`:

   ```gitignore
   # whiteboard local state: scene, calibration, snapshots, Edge profile, logs, API token; per-machine config
   tools/whiteboard/.state/
   tools/whiteboard/whiteboard.toml
   ```

## Running

- `uv run whiteboard serve` runs the daemon in a terminal until Ctrl+C. It:
  - serves the board page on `127.0.0.1:8770`
  - opens it fullscreen in an Edge kiosk on the projector
  - starts the camera, the change watcher and the board agent
- You don't have to start it by hand. The first `board_*` tool call (or `whiteboard look`, `draw`, ...) starts it in the background, with its log in `.state/daemon.log`. Just loading `.mcp.json` doesn't start it.
- `uv run whiteboard stop` stops a running daemon cleanly. It closes the kiosk and frees the camera.

## Aiming the camera

Put the webcam where it sees the whole board, including all four edges and a little wall around them, as straight on as you can. Keep yourself out of the way while calibrating.

- **Live:** `uv run whiteboard camera view` opens a window with the camera's raw view at about 5 fps, so you can aim it while you watch. Close the window or press q to stop. Nothing flashes on the board.
- **One photo:** `uv run whiteboard look --raw`. Before calibration, that saves the raw camera frame and prints its path.

### The live stream (`GET /api/camera/stream`)

The window reads the daemon's camera stream: `multipart/x-mixed-replace` JPEGs, about 5 fps, scaled to 960 px wide, raw (no rectification). It reuses the frames the daemon already grabs, so the camera is never opened twice, and it never blanks or flashes the projector. Like every `/api/` route it needs the `X-Signal-Token` header, never a token in the URL. It answers 503 when the camera is off or has no live frame, and 429 past 2 open streams. A stream ends when its viewer goes or the daemon stops. A future "Connected devices" page in the Signal console will proxy this stream, so the browser never holds the token.

## Aligning to the board

Do the optical part first, because software can only fix what's left:

1. On the projector, set the **optical zoom, position and keystone** so the picture covers the whole board, roughly square, with as little spill onto the wall as possible.
2. Run `uv run whiteboard calibrate`. It:
   - projects ArUco markers, finds them in the camera image and saves the camera-to-projector mapping
   - blanks the page and photographs the board
   - finds the board's outline and warps the projection onto it, with black outside the board

   It prints the reprojection error and whether the board outline was found.
3. Check it with `uv run whiteboard fit show`, which projects the fitted outline for 10 seconds.

If the markers aren't found, the camera can't see the projected area: aim it at the board and try again. If the board outline isn't found, look at `whiteboard look --raw` (projector coordinates once calibrated), read off the board's corners and set them by hand:

```
uv run whiteboard fit --quad 140,60,1140,60,1140,560,140,560   # TL, TR, BR, BL in projector px
```

`whiteboard fit` re-detects the outline and `whiteboard fit clear` removes the fit. Claude can do the same with `board_look(raw=True)` and `board_fit(quad=[...])`.

Coordinates: everything Claude draws is in **board pixels**, the same space as `board_look` images. Without a fit that's the projector's 1280x720. With a fit it's the logical board, `fit_height` (720) tall and as wide as the board's aspect ratio. `GET /api/status` reports the size.

### It re-aligns itself

With `[align] auto = true` (the default), the daemon checks now and then that the board is still where the fit says it is:

- **When it checks:** on every photo the change watcher takes, plus every `check_s` (30 min) while the board is idle (nothing moved and the daemon changed nothing on the page for 30 s, and no Claude turn running). It finds the board outline in a blank-page photo and measures how far its corners are from where the fit puts them, in camera pixels. Only OpenCV, no Claude. While the room is too dark to read the board (`[watcher] dark_floor`), neither this timed check nor the marker check below runs; they catch up once the light is back. `whiteboard align` and `whiteboard realign` always run.
- **When it acts:** two checks in a row over `drift_px` (15 px). A single odd check (someone leaning on the board) does nothing, and so does a check that can't see the board's edges. Then, once idle, it re-runs the calibration (the markers flash for about a second), re-fits the board and shows "Re-aligned to board" for 3 seconds.
- **What's safe:** it keeps the old alignment if anything fails (too few markers, reprojection error over `max_reprojection_px`, outline not found, or not matching what the check saw) and logs why. Your drawings stay on the same spot of the board, because they're stored in board coordinates.

- **The projector:** a blank photo can't show the projector moving, so every `marker_check_s` (1 h) while idle the markers flash for about a second and are solved again. If the projector moved, the fit is carried over to the new mapping. That's only done when a photo shows the camera stayed put; it's compared with one kept from the last good alignment (`.state/align-reference.png`).

`whiteboard realign` (or `board_realign`, or writing "realign" on the board) does that marker check right away and prints what changed. `whiteboard align` only measures the photo drift. If the camera moved and the board's outline can't be found, it keeps the old alignment and says so: run `whiteboard calibrate`.

## Saving boards

Save a board to pull it up again later, e.g. an old diagram:

- `whiteboard save NAME [--description TEXT] [--overwrite] [--refresher tasks|todo]` keeps a copy of the projected items. When calibrated, it also takes one clean photo and extracts your marker strokes from it as bright strokes on a transparent background (black ink turns white, coloured ink keeps its hue). Without calibration it saves the items only and says so. A taken name is refused unless you pass `--overwrite`.
- `whiteboard load NAME [--overlay] [--no-ink]` puts the items back (replacing the current ones unless `--overlay`). It projects your saved strokes over the whole board. If the board's size changed since, everything is scaled to fit.
- `whiteboard saves` lists them, newest first. `whiteboard delete-save NAME` removes one.

Claude has the same as `board_save`, `board_load`, `board_saves` and `board_delete_save`. The board agent uses them when the board says "save this as X" or "pull up X". Saves live in `.state/boards/<slug>/`.

A save can name a `refresher`, what redraws it from live data: `tasks` (the task grid, `board_tasks_show`) or `todo` (the to-do list). It's a fixed choice, never a command, and an unknown one is refused when saving and when reading `meta.json`. The Signal console shows an Update button on saves that have one, which redraws the board (`whiteboard tasks show` or `todo show`) rather than loading the old save.

## The task grid

`board_tasks_show` (CLI `whiteboard tasks show`) clears the board and draws every task the orchestrator reports (the console's `tools/console/.state/tasks.json`, written with `console tasks set`), plus the usage line from tools/usage. It's the "agent-task-grid" layout coded once (`src/whiteboard/tasks_grid/`): boxes ordered by % done, queued and done grouped in the last boxes, a bold white status number in each box (1 review, 2 building, 3 needs you, 4 queued, 5 done) with the key in the header, and `YOU:` in a box that waits on the owner. It never loads a save, so no stale snapshot or ghost ink comes back. It hides the TODO view first if it's up.

## The TODO view

The board can show the owner's TODO list instead of the projected items, read live from the week plans in `life/`:

- **Keynotes**: today's 2-4 AI-written lines on what matters most and why, in a block under the header (see "Keynotes" below). None on a day without them.
- **Overdue**: everything under the plan's `## Overdue`, plus any open item past its due day. Only items at most 7 days late show, newest first, 5 at most, with how late they are ("3d late"); older and undated ones are folded into the heading ("Overdue · +2 older") so they don't crowd out what's due now.
- **Today**, **Tomorrow** and **This week** (the rest of the 7 days ahead), sorted by time (untimed items last on their day). This week's rows show the day and time ("Wed 14:30").
- **Work items of note**: items under a `## Of note` section that are due later or have no date.

Each row has its tag as a coloured chip (a course keeps its colour), a short title, and the due time or date. The title is cut down by code, never a model: struck-through done parts, long parentheticals (file lists, status notes) and trailing source tags like `(site)` or `(mail)` are dropped, and a title still over 40 characters is cut at its first comma, semicolon, colon or dash that keeps at least 20 characters, else at a word near 40 with `…` (`todo/view/titles.py`). Claude still gets the full text from `board_todo_show`. Undated items outside `## Of note` aren't shown. It reads this week's plan and next week's if it exists. Due notes can be `(due 2026-10-21 08:30)`, `(due 2026-10-21)`, `(was due ...)` or `(due Thu)` (that day of the plan's week).

Switching:

| | Claude | CLI |
|---|---|---|
| Show the list (re-read `life/` first) | `board_todo_show` | `whiteboard todo show` |
| Back to the items | `board_todo_hide` | `whiteboard todo hide` |
| Re-read `life/` without switching | `board_todo_sync` | `whiteboard todo sync` |
| Tick / untick an item | `board_todo_done(item)`, `board_todo_undone(item)` | `whiteboard todo done ITEM`, `todo undone ITEM` |

Your items are only hidden, never touched, so switching back is instant. Drawing, moving or loading a board also switches back. The view survives a daemon restart. `item` is an id (sync and show list them) or a piece of the text only one item has, e.g. `A19`.

When an item gets ticked in `life/`, the next sync crosses it out with a short animation and dims it, with a check mark in its box and "✓ done" in place of its due text. It stays there, in place, for the rest of the day (so a marker line on the board keeps lining up with it); the next day's sync drops it. A daily sync runs at 06:00 as a scheduled task, right after the keynotes: see [schedule/README.md](schedule/README.md). It only refreshes a running daemon. A daemon also syncs when it starts.

**Crossing out on the real board.** While the list shows, draw a line through an item with a marker. When the change watcher next takes a clean photo, the daemon looks for new ink running through the middle of a row across most of its text. If it finds some, the daemon takes one more photo with the list projected, and a quick `[agent] triage_model` check looks at the before and after photos with the rows boxed, plus that projected one. An item counts only when the new line visibly runs through its own projected words, so a slightly-off calibration is unlikely to tick the row next to the one you crossed out. If it confirms, the item's checkbox is ticked in its week plan and the board animates it. If it isn't sure, the row shows a dashed `done?` instead and nothing changes; say "done" to Claude (`board_todo_done`) to confirm. A row next to one with the same text (say `Quiz 3` under two courses) only ever gets the hint, since a slightly-off line can't tell the two apart.

A change is only checked when the list showed, with the same rows in the same places and the same alignment, both in the photo before you drew and in the one after; when the change erased next to no ink near the rows (the photo's outer edge flickers, so it's ignored); and, with `[align] auto` on, when the drift check didn't find the board moved in that photo. Anything else goes to the board agent and ticks nothing: a sync that moved rows (from any session, or a plan edit), switching to the list from the items, a re-align, or a camera bump (old ink shifts, so ink is erased; the board's frame may slide into view). So that the first line you draw after showing the list still has a "before", showing it takes one clean photo straight away (a brief blank flash). After a daemon restart with the list already up, a re-align, or a sync that moved rows, there's no such photo, so the first change after it only becomes the "before" and your cross-out needs redrawing or `board_todo_done`. The daemon log says why each change wasn't checked or found nothing (`TODO cross-out check: ...; passing it on`).

What's left is unlikely, not impossible. If the alignment is off by most of a row without the drift check noticing, and the model misreads the projected words, the row next to yours can be ticked. A line started in the split second between a photo and a sync that moves the rows is matched against the new rows. Each tick is logged to `.state/todo.log`; undo a wrong one with `board_todo_undone`.

That's the owner's call: a confirmed cross-out greys out and saves to `life/` straight away, and if the wrong row greys out the owner tells the voice agent, which undoes it with `board_todo_undone` (its reply names the item). The owner accepts that small risk of a wrong tick rather than confirming every cross-out.

That ticking is the whiteboard's only write to `life/`:

- only this and next week's `plan.md` inside `life/` (links and junctions are resolved first), only the `[ ]` mark of the item's line;
- the plans are read fresh and the item found by its id (a cross-out uses the id only, never a text match), so a line edited since the last sync is still ticked while its tag and text stay the same;
- it's refused (HTTP 409) only if the plan changes during the edit, so the line is gone or now there twice, or the file changes between reading and writing it; the owner's edit is never overwritten;
- each change is logged to `.state/todo.log`.

The cross-out check runs only while the board agent is on (`[agent] enabled`), since it calls the same `triage_model`. With the agent off, no model is called at all, and crossing out does nothing; use `whiteboard todo done` instead.

Your ink stays on the board; wipe it whenever you like, erasing never un-ticks anything. To undo, use `board_todo_undone` or `whiteboard todo undone`. The board agent has to ask you before it may use `board_todo_done` or `board_todo_undone` itself, since anyone can write on the board.

## Keynotes

Every morning at 06:00 the scheduled task runs `whiteboard keynotes`: one Claude call (Sonnet, no tools, no settings files) reads the day's plan items, grouped the way the TODO view groups them, plus the week's first priorities, and writes 2-4 short lines on what matters most today and why to `.state/keynotes.json`. The plan text goes to the model framed as data, never instructions. Run `whiteboard keynotes` any time to write them again; it refreshes a running daemon and never starts one.

Showing them is plain code: the TODO view puts them under its header, and the idle view shows them in the priorities' place (priorities come back on a day without keynotes). The file is only shown on the date it was written for, so a stale, missing or broken file shows nothing, never an error. See `src/whiteboard/keynotes/README.md`.

## The idle view

When nothing is drawn, the board shows a calm dashboard instead of black: a dial and `HH:MM` clock with the date, the weather, today's tasks, today's keynotes (or the week's priorities), the agents' tasks with the usage line, upcoming dates and a news ticker. Everything updates by itself from code; the daemon never calls a model for it (the keynotes are written once a morning by the scheduled task, outside the daemon). The look is the approved design in `refdocs/research/idle-board/`.

- **When it shows:** once the items view has had nothing drawn for `[idle] empty_s` (10 s); the "thinking" box doesn't count, and shows over it. Drawing, moving or loading a board brings your items back. The TODO view works as before, and the night view still wins: under it, the idle view only becomes the view the night goes back to.
- **When you draw:** new ink on the board (at least `[idle] ink_min_ratio` of the board in added ink, so daylight and camera noise don't count, erasing never does, and slow writing adds up; never a minute flip or the daemon's own page change) while the idle view shows switches to the empty items view, a black page, so your ink is clear. The board agent still gets the change and may draw an answer. The idle view only comes back once no new ink has been seen for `[idle] ink_quiet_minutes` (10) and nothing is projected, or as soon as a photo shows the ink wiped off again.
- **By hand:** `board_idle_show` / `board_idle_hide`, or `whiteboard idle show|hide|sync` (`sync` re-reads every source now). On an empty board, hiding it only lasts `empty_s`.
- **Where each part comes from:**
  - clock and date: the page's own clock, on each minute (no seconds; each minute flip counts as a page change, so the camera never takes it for drawing);
  - today and upcoming: the week plans in `life/` (the 2 newest overdue items, with the full overdue count in the heading, then today, then the next days; short titles as on the TODO view), plus Google Calendar events from `tools/calendar/.state/agenda.json` when it's fresh (under 2 h; else plan items only), chipped "Cal";
  - keynotes: today's `.state/keynotes.json` (above), in the priorities' place; without them,
  - priorities: the first 3 lines of this week's `## Priorities` that aren't past due, with struck-through done parts dropped (a line that's all done is skipped);
  - agents: the console's task list and the usage line, as on the task grid;
  - weather: Open-Meteo (keyless, °F) for the PC's place, found by an IP lookup at start and every `[idle] locate_hours` (else Springfield, IL); cached 30 min in `.state/idle/`, an older reading up to 6 h shows "as of", then "Weather unavailable";
  - news: the first 6 headlines from the last 24 h of `[idle] news_feed` (AllSides by default; RSS 2.0 or Atom, switchable in config), titles only, cleaned and shown as plain text, scrolling right to left along the footer like a TV news crawl at `[idle] ticker_px_s` (75 design px a second), with the source name fixed beside it. New headlines join where the list starts over, so it never jumps. The camera's motion check leaves the ticker's band out, so its scrolling never counts as someone drawing or keeps the drift monitor from seeing the board idle; ink drawn over it still shows up in the next photo.
- Files are re-read when they change (checked every 15 s); weather and news refresh every 30 min in the background. The page is only sent new data when something changed, just after the minute turns (with the clock's flip), so the camera's checks still get their quiet time. A source that fails keeps what it showed and is logged once.

- **What leaves the PC:** keyless HTTPS requests to ipapi.co, Open-Meteo and the news feed (AllSides by default), each of which sees the PC's public IP; Open-Meteo also gets the place's coordinates. Nothing else is sent. To stop the IP lookup, set `[idle] locate = false` (the weather then uses `place`, `lat` and `lon`).

See [src/whiteboard/daemon/idle/README.md](src/whiteboard/daemon/idle/README.md) for the details and `[idle]` in `whiteboard.example.toml` for the settings.

## The night view

Sleep mode (`tools/sleepmode`) puts a very dim night sky on the board while you sleep, a new one each night: warm stars, a Milky Way with coloured nebulae, the moon at its real phase, and 3 or 4 slow effects picked for the night from a pool (constellations, planets, aurora, fireflies, a passing cloud, a comet and more). Everything comes from the date and the clock, with no model and no network (the renderer is in `src/whiteboard/display/static/night/`, its README has the brightness cap and the pool). Like every other view it's drawn inside the board fit, so it sits on the whiteboard and the wall stays black. It's a third view, next to the items and the TODO view:

| | Sleep mode | Claude | CLI |
|---|---|---|---|
| Show the sky, or a black page | `POST /api/night/show {"seed", "sky"}` | `board_night_show(sky)` | `whiteboard night show [--no-sky]` |
| Back to the view it hid | `POST /api/night/hide {}` | `board_night_hide` | `whiteboard night hide` |

- `seed` picks the sky. Sleep mode sends `YYYYMMDD` of the evening the night began; Claude and the CLI send none, which means tonight's. `sky: false` is a plain black page. Showing it again only changes the sky.
- Hiding goes back to the view that showed before, items or TODO. Outside the night view it changes nothing and still says ok, because wake calls it every time.
- The view, the sky and the view under it are saved in `scene.json`, so a restarted daemon comes back to the night sky.
- Like every board command, `whiteboard night show|hide` and `board_night_*` start the daemon if it's stopped, so the projected items can show for a moment before the sky. Sleep mode never starts it.

While it shows, nothing flashes or wakes things:

- The change watcher takes no photos, so the board agent, its triage and the TODO cross-out check get nothing to look at. The drift monitor runs no checks, re-aligns or marker flashes.
- Anything else that would flash is refused with HTTP 409: the blank, pattern and fit modes (so `board_look` with `clean=true`, calibrate, realign, `fit auto`, `fit show` and `align`) and highlights. `board_look(clean=False)` and setting the fit by hand (`fit --quad`, `fit clear`) still work, and `board_save` saves the items without a photo.
- Drawing, moving, loading a board and switching to or from the TODO view still work, hidden under the sky: they only change the view the night view goes back to. So nothing lights up the projector until sleep mode ends; then the board shows what it would have shown.
- Afterwards the watcher and drift monitor carry on. The drift monitor counts the night view ending as a page change, so a check or marker flash that came due overnight waits 30 s after you wake instead of flashing at once.

## The change watcher

With `[watcher] enabled = true`:

1. Once a second, the daemon compares camera frames to notice someone drawing.
2. When nothing has moved for `stable_s` (4 s), it briefly blanks the projection (`blank_ms`, 250 ms). That lets it photograph only your ink.
3. It compares that photo with the previous clean one. If the ink changed enough, it hands the snapshot and the changed region to the board agent.

Claude's own projections never count as ink, because only blank-page photos are compared. Each photo flashes the board, so it keeps them rare:

- For `settle_s` (3 s) after the daemon changes the board itself (any blank, a marker check, a drawing, the TODO view), nothing the camera sees counts as motion. So its own flashes, and the camera's exposure catching up after them, never cause another.
- While the night view shows, it takes none at all.
- Photos are at least `min_interval_s` (30 s) apart, unless a lot of new ink (10x `ink_change_ratio`) is already visible.
- While the room is too dark to read ink (the camera's median grey under `dark_floor`, 30), it takes none at all and logs that once.
- Exposure and room-light changes, dim-room sensor noise and the flickering edge of the photo don't count as ink, while new ink still counts across a change of light.
- The idle view's scrolling news ticker isn't motion: its band is left out of the live comparison.

## The board agent

Each board change first goes through a cheap **triage**: a one-shot, tool-less call to `[agent] triage_model` (default `haiku`) that looks at the snapshot and answers whether the new writing is meant for Claude. If not (notes, erasing, shadows), the change is logged and skipped. If triage errors, takes longer than `triage_timeout_s` (15) or answers badly, the turn runs anyway. `triage = false` turns it off.

A change that passes triage gets a **fresh Claude session** (`[agent] model`, default `sonnet`), so old board images never pile up in the context. The turn includes the snapshot image, the changed region and the items already projected. If the turn drew or changed anything, the daemon takes one look with the projection on and sends it to the same session as a verify turn ("is it placed right?"); the verify turn never triggers another. `verify_after_draw = false` turns that off. A turn still running after `turn_timeout_s` (300, above the 120 s permission dialog) is given up and its session closed, so a hung CLI can't leave the agent stuck.

While a turn runs, a dashed "Claude is thinking" box (scene item kind `loading`, id `loading`) sits beside the changed region. The agent can move it with `board_placeholder`; it disappears at the first draw or when the turn ends, and `board_save` never keeps it.

The agent acts on requests, questions, tasks and diagrams meant for Claude. It ignores everything else. It projects its reply in empty space beside your work, and it can say one short sentence through audiohub `notify`. One turn runs at a time; changes made during a turn are merged into the next.

The whiteboard tools (except ticking TODO items and the night view's show and hide), `notify`, `ToolSearch` (it only loads the whiteboard tools' schemas, which the CLI defers) and a Read of that turn's own snapshot run without asking. Anything else, including every other file read or search, pops up a topmost Allow/Deny dialog (`signal_confirm`) that defaults to Deny and denies by itself after 120 s.

**To turn the agent off**, set this in `whiteboard.toml`:

```toml
[agent]
enabled = false
```

Changes are then only logged, and the TODO view's cross-outs aren't checked. Set `[watcher] enabled = false` to stop watching altogether. The `board_*` tools keep working either way.

## Security

The daemon only listens on loopback, but any web page you visit could still send it requests. Several layers stop that:

- **API token.** Every `/api/*` request must carry the token from `.state/token`; the MCP server and CLI read it. Cross-origin requests are refused. The daemon claims its port before writing the token, so a second `serve` can't overwrite it. The token file is readable by your Windows account only: inheritance is removed and only you are granted access.
- **Page cookie.** The kiosk opens `/board?token=...` once. That sets an HttpOnly, SameSite=Strict cookie (an HMAC of the token) and drops the token from the URL. Everything outside `/api/` (the page, static files, snapshots, `/ws`) needs that cookie, and `/ws` also only accepts the board page's own origin.
- **The board is untrusted.** Anyone in the room can write on it, so the board agent treats board text as content, not orders. It won't reveal tokens, secrets or file contents because the board asks, and it declines risky requests on the board. Its own allowlist is enforced by a PreToolUse hook, so "don't ask again" rules from your interactive sessions don't apply to it (it loads project settings only). Every file read, glob or search asks first. The one exception is a Read whose path is exactly that turn's snapshot.

## State (`.state/`, gitignored)

| File | What it holds |
|------|---------------|
| `scene.json` | The projected items, the board fit and the view (items, TODO, or night with its sky and the view under it; the idle view is saved as items and comes back by itself). |
| `todo.json` | Which TODO items were done since when (so yesterday's done items drop off) and which were open at the last sync. |
| `todo.log` | Every checkbox the board ticked or unticked in `life/`. |
| `idle/` | The idle view's weather and location caches (`weather.json`, `location.json`). |
| `calibration.json` | The marker calibration. |
| `snapshots/` | The last `keep_snapshots` photos. |
| `boards/` | Saved boards, one folder each (see `src/whiteboard/saves/README.md`). |
| `edge-profile/` | The kiosk's own Edge profile. |
| `daemon.json` | The running daemon's pid and port. |
| `token` | The API token. |
| `align-reference.png`, `.json` | A blank photo from the last confirmed alignment, for telling a camera move from a projector move. |
| `daemon.log` | Output of a daemon started in the background. |

## Packages (`src/whiteboard/`)

`config`, `shared` (small helpers several packages use, like the atomic file write), `display` (scene, server, screen and the board page), `camera`, `agent`, `saves`, `todo` (the TODO view's parsing, layout and strike geometry), `idle` (the idle view's rules and sources), `daemon` (with `daemon/todo`, the view's controller, routes and cross-out check, and `daemon/idle`, the idle view's refresh loop and routes), `daemon_client`, `mcp_server`, `cli`. Each has a README. Tests mirror them under `tests/`: `uv run pytest`. The page tests (`tests/display/static/`: the TODO view, the idle view, the night sky and the board page's view wiring) run headless Edge and skip themselves where Edge can't start (some sandboxes).

`schedule/` holds the 06:00 morning run's scheduled task scripts (keynotes, then the TODO sync). `keynotes` (the day's AI-written lines) has its own README too.
