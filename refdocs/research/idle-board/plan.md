# Idle board: data and wiring plan

> Built in `tools/whiteboard` (`src/whiteboard/idle/`, `daemon/idle/`, `display/static/idle/`) and `packages/weather`. Where this plan and those READMEs differ, the READMEs are current.

Research for the projector's default "idle board": today's tasks, time/date, weather, key notes, one headline, agent tasks, upcoming dates. Visuals are the designer's job; this covers data, refresh and wiring. Read with `tools/whiteboard/README.md` and `refdocs/research/brief-me.md` §7.1, §8 and §9 (the brief's board page, weather and calendar plans overlap this).

**Hard rule (the owner):** every region updates by itself from code on a timer or a file change. No LLM in any refresh path, and nothing on this board needs one. Where a region could have used a model ("key notes", "key headline"), a fixed rule picks it instead (§2).

## 1. View wiring

### A fourth view, `idle`

- `display/scene/model.py`: add `IDLE_VIEW = "idle"` to `VIEWS` and `DAY_VIEWS`. Then the night view can hide it and come back to it with no new night code (`switch_view`, `show_night` and `hide_night` already work on `DAY_VIEWS`).
- `scene.json` saves the view as it does now. Rollback note: older code rejects an unknown view, as with `night` (see the comment in `display/scene/store.py`), so the store writes `items` to disk when the view is `idle`. `idle` is a default, not a choice anyone needs kept.
- `BoardController` (`display/server/board/controller.py`) gets `set_idle(payload)` and `idle_message()`, like `set_todo`/`todo_message`. The data is rebuilt, never saved. The page message is `{type: "idle", idle}`.
- Daemon: new `daemon/idle/` with `controller.py` (IdleController: refresh loop, builds the payload, pushes only when it changed) and `routes.py`: `POST /api/idle/show`, `/api/idle/hide` (back to items) and `/api/idle/sync` (rebuild now). They sit behind the usual token guard, and `serve.py` wires them like `daemon/todo`.
- Page: `display/static/idle/idle.js`, `idle.css` and small region modules (`clock.js`, `render.js`). Add an `#idle` container to `board.html`; `board.js` dispatches `type: "idle"` and shows or hides the container in `setView`. Every string goes in through `textContent`, as `todo.js` does.
- MCP: `board_idle_show` and `board_idle_hide` in `mcp_server/board_tools.py` and `app.py`, with descriptions in `descriptions.py`. CLI: `whiteboard idle show|hide|sync` in `cli/commands/idle.py`. `daemon_client/http_api.py` gets `api.idle(action)`.
- Optional later: a console button through `/api/action`'s fixed list.

### What "default" means: one rule

**The board shows `idle` whenever the items view has had no items (ignoring the `loading` box) for 10 s.**

- This covers daemon start with an empty scene, `board_clear` and `todo hide` onto an empty board, and nothing else needs a timer.
- The 10 s debounce stops a flicker in clear-then-draw sequences: `draw_task_grid` calls `api.clear()` and then `put_item`, and `load` replaces the items.
- It's checked in IdleController's loop, a pure `should_go_idle(scene, empty_since, now)`, and applied through `switch_view(scene, IDLE_VIEW)`.

How it yields to the other views:

- **Items:** drawing, moving or loading a board switches to items. `show_drawn_items` already does this for any non-`loading` item. The board agent's "thinking" box must not leave idle, and that already holds, so the page draws a `loading` item above the idle layer.
- **TODO:** `todo show` switches as before. `todo hide` goes to items, and the rule brings idle back 10 s later.
- **Night and sleep mode, night still wins:** `show_night` from idle saves `previous_view = "idle"`, and `hide_night` goes back to it. Under the night, the auto rule only changes `previous_view`, which `switch_view` already does. The night refusals don't change. Payload pushes under the night update the hidden data and light nothing.

Rejected options:

- "After N minutes with no board activity": it would hide a diagram the owner is still using.
- "Always at daemon start": it would hide restored items.

### Camera and drift interplay (must handle)

- **Pushes:** each payload push counts as a page change through `_broadcast`, which triggers the watcher's 3 s settle and resets the drift monitor's "page unchanged 30 s" idle rule. Push only when the payload really changed, and at most once every 60 s, except for a view switch.
- **The clock:** it ticks in the page, so the daemon doesn't see it change, but the camera does. A large clock flipping `:59` to `:00` could pass `motion_ratio` (1%). Fixes:
  - Show `HH:MM` with no seconds.
  - Have `page_changed_s()` treat each minute boundary as a page change while the view is `idle`: return `max(changed_s, last_minute_boundary_monotonic)`. This is one small pure function, tested.
  - Ask the designer to keep the clock digits moderate in size and thin-stroked.
- **Light on the board:** the board is for marker ink, so no filled areas. Use thin, bright text, as the existing rule for every projection already requires.
- **Cross-outs:** the idle task list is read-only for now. Cross-out ticking stays a TODO-view feature (its strike checks rely on the TODO layout).

## 2. Data sources

All refreshes run in IdleController's asyncio loop. File sources are checked by `stat().st_mtime_ns` every 15 s, which costs almost nothing. Network fetches use `aiohttp.ClientSession`, which the daemon already has as a dependency, with a 4 s timeout and a 512 KB body cap. Each source fails on its own, and the payload carries `as_of` and `stale` for each region.

| Region | Source | Refresh | Failure / empty | Secrets / network |
|---|---|---|---|---|
| Today's tasks | `whiteboard.todo.source` (`find_week_plans`, `read_week_entries`) + `whiteboard.todo.view.sections.build_groups(entries, today)`; keep the `overdue` group and today's ISO-date group, open (`[ ]`) items only | mtime of this and next week's `plan.md`, every 15 s; plus the date rolling over at midnight | Plans unreadable: keep the last list and mark it stale. None due: "Nothing due today" | none (local) |
| Time / date | Page JS, the PC's local time zone (`America/New_York`) | `setTimeout` to the next minute boundary, then every 60 s; the date comes from the same tick | none | none |
| Weather | Open-Meteo (keyless), `api.open-meteo.com/v1/forecast?latitude=..&longitude=..&current=temperature_2m,weather_code&daily=temperature_2m_max,temperature_2m_min,precipitation_probability_max,weather_code&temperature_unit=fahrenheit&timezone=America/New_York&forecast_days=1`, the brief plan's §8 call | 30 min (`.state/idle/weather.json`) | Failed fetch: the cache up to 6 h old ("as of 05:40"), else "weather unavailable" | Outbound HTTPS, no key; sends only coordinates |
| Key notes | The current week plan's `## Priorities` numbered list (deterministic, already kept up by agents and the owner): first 3 lines whose `(due ...)` dates aren't all before today, tag shown as a chip | plan mtime, every 15 s | No section or nothing left: hide the region | none |
| News | One feed, `[idle] news_feed` + `news_source` (switchable without code; RSS 2.0 or Atom). The default is AllSides: `https://www.allsides.com/rss/news`, label "AllSides" (keyless RSS 2.0). Ground News has no free public feed | 30 min (in memory) | Failed: keep the last headline up to 6 h, else "No headline" | Outbound HTTPS only. See sanitising below |
| Agent tasks | `signal_tasks.read_tasks` + `group_tasks` on `tools/console/.state/tasks.json` (already a dependency, as the task grid uses it); plus `read_usage` on `tools/usage/.state/usage.json` for a one-line usage summary | mtime of both, every 15 s | Missing: "No agent tasks". `StateFileError`/`None`: keep the last copy (the usage reader rule) | none |
| Upcoming dates | Now: the next 7 days of dated items from the same plan parse (`build_groups` day groups after today), plus today's and tomorrow's rows from `life/terms/<term>/schedule.md` (the class table, `TODO` cells skipped) | plan and `schedule.md` mtime, every 15 s | Nothing: "No dates this week" | none |

Notes:

- **The key headline:** the first `<item>` in feed order, which is the editor's ranking. Skip it if the title is empty or `pubDate` is over 24 h old, then take the next. No model and no summary: only the title and the source name are shown.
- **Sanitising the news feed:**
  - Reject a body containing `<!DOCTYPE` before parsing, and parse it with `xml.etree.ElementTree` (Python 3.12's expat guards billion-laughs; the DOCTYPE check rules out entity tricks).
  - Take only `channel/item/title` and `pubDate`. Strip any tags, `html.unescape` it, drop control characters, collapse whitespace and cut to 140 characters.
  - The page sets it with `textContent` and shows no link.
  - It's data only, never passed to a model.
- **Weather location:**
  - `life/` names no city. the example location is Springfield, IL (39.7817, -89.6501); set your own in `[idle]`.
  - Put it in `whiteboard.toml` `[idle] lat/lon` as the default. Don't geocode by name: Open-Meteo ranks Springfield, Tennessee first.
  - Upgrade: read `life/me/location.md` once the brief's `set_location` (brief-me §8) lands.
  - Show the current °F, a condition word from a fixed WMO `weather_code` table (with an icon and always a word, since the owner is colourblind), today's high and low, and the rain chance as a percentage.
- **Weekly-plan todos:** `## Overdue` items that are already `[x]` are excluded (open items only). This matches "today/overdue".
- **Calendar access today:**
  - The mail tool's OAuth has only `gmail.readonly` and `gmail.compose`, with no calendar scope.
  - The claude.ai Google Calendar connector runs only through a model, which breaks the no-LLM rule and can't run headless.
  - No ICS URL is configured. So use `life/` now.
  - **Upgrade path:** the planned `tools/calendar` (brief-me §9: the same OAuth client, with `calendar.events.readonly` and `calendar.calendarlist.readonly`, a DPAPI token, and `calendar agenda --json` cached 10 min). The idle board reads that cache file and never holds a token.
  - A private Google ICS URL is a fallback only. It is a secret (DPAPI or an owner-only `.state` file, never `whiteboard.toml`), and its RRULE expansion needs extra dependencies.

## 3. Where the code lives, caching, tests

- **`packages/weather` (`signal_weather`, new, stdlib `urllib` + `signal_jsonstate`):**
  - `forecast(lat, lon, tz, cache_path, now) -> Weather | None`, the WMO code-to-word table, and the 30 min and 6 h cache rule.
  - It's a package because the brief's phase 3 morning brief needs the same call (real reuse, codingrules §2). The daemon calls it in an executor.
- **Whiteboard `src/whiteboard/idle/`** (pure, no I/O beyond reading files):
  - `sources/` (todos-today, priorities, schedule rows, news parse and sanitise, tasks summary)
  - `payload.py` (the JSON for the page)
  - `rules.py` (`should_go_idle`, the minute-boundary page change)
  - news fetching lives here too, since only the board uses it.
- **`daemon/idle/`:** the controller loop and routes, kept apart as `daemon/todo` is.
- **Cache:** `tools/whiteboard/.state/idle/{weather,news}.json`, atomic writes (`whiteboard.shared.files` / `signal_jsonstate`), already gitignored by `.state/`. Nothing else is persisted.
- **Config:** a new `[idle]` section with `enabled`, `lat`, `lon`, `news_feed`, `empty_s = 10`, `weather_min = 30`, `news_min = 30`, mirrored in `whiteboard.example.toml`.

Tests (about 6, per AGENTS.md §6; fake HTTP and files, no network):

1. `should_go_idle` and the view transitions, parametrized: empty for 10 s goes to idle; a `loading`-only board still counts as empty; drawing leaves idle; night over idle returns to idle; under night, idle only changes `previous_view`.
2. The news parser, parametrized: picks the first fresh item, skips stale or empty items, refuses a DOCTYPE and oversized bodies, and strips markup and control characters (a security boundary).
3. The weather cache fallback: fresh fetch, failed fetch within 6 h shows "as of", failed past 6 h shows unavailable.
4. Todos-today and upcoming selection from a fixture plan: overdue open items, today's items, next 7 days, ticked items dropped.
5. Priorities filtering: past-due lines dropped, capped at 3.
6. `page_changed_s` minute-boundary rule while idle (it guards the camera from false motion).
7. One headless-Edge page test, as the TODO view has: idle renders the payload with `textContent` and the clock ticks.

Skip tests of the CLI and MCP pass-throughs and of constants.

## 4. Needs the owner

- **Location:** confirm the example place as the weather spot, and °F.
- **News:** decided: AllSides (`[idle] news_feed`/`news_source`, switchable).
- **Key notes:** OK with the week plan's `## Priorities` (top 3, not past due) as the source? If the owner would like a separate daily notes spot, say where (for example a `## Today` section in the plan).
- **Calendar:** life/ schedule plus plan due dates for now. The real calendar needs the `tools/calendar` setup (a Google consent for the read-only calendar scopes, brief-me §9), or a private ICS URL the owner pastes the owner (kept out of git and chat logs).
- **Clock size:** OK with a modest `HH:MM` and no seconds (a big or ticking clock can wake the camera's motion check)?
