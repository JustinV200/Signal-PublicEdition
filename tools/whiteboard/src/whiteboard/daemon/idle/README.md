# whiteboard.daemon.idle

The idle view inside the running daemon: keeps its data fresh, applies the default rule, and exposes `/api/idle`.

## Public API

- `IdleController(board, settings.idle, IdleFiles(...), hooks=None)`:
  - `start()`: reads the files once, then runs a loop every second (`stop()` cancels it and any fetch in flight).
  - The default rule: once the items view has had nothing drawn (the "thinking" box aside) for `[idle] empty_s`, it switches to the idle view. Under the night view it only changes the view the night goes back to. Drawing switches back to the items (`scene.show_drawn_items`). `[idle] auto = false` turns the rule off.
  - Ink on the physical board: `note_ink()` switches the idle view (if it shows) to the empty items view, a black page, so the owner's marker ink is clear, and holds the default rule off until no new ink has been reported for `[idle] ink_quiet_minutes` (10) and nothing is projected. `note_wiped()` ends that early; `is_holding_off` says whether it's on. The board agent still gets the change and may draw an answer; the TODO and night views are unaffected (the watcher takes no photos at night).
  - `show()`, `hide()`, `sync()`: switch to it, back to the items (on an empty board the rule returns in `empty_s`), or re-read every source now. Each returns `summary()`: `{ok, view, tasks, priorities, keynotes, agents_active, upcoming, weather, place, headline}`, counts and flags only, so no plan or feed text reaches a model.
  - Pushes (`BoardController.set_idle`) happen only while the idle view shows, only when the data changed, and only on the first tick after a minute boundary (with the page's clock flip, which already counts as a page change), except right as the view comes up. So the drift monitor still gets its quiet 30 s each minute.
- `InkWatch(idle, ink_min_ratio, downstream)`: the change watcher's `on_board_changed` and `on_clean_frame` (`watcher_tasks`). Every reported change goes on to `downstream` (the cross-out check or the agent) unchanged; an idle failure is logged and never keeps the change from it. The watcher only compares blank-page captures, so minute flips, the idle page and the daemon's other page changes never count. One report can't tell ink from noise by size (the watcher re-baselines on every report, so slow writing arrives in small pieces), so InkWatch compares captures itself, counting only ink added (`added_ink_ratio`; erasing never counts as new ink). Its rules:
  - **New ink:** at least `[idle] ink_min_ratio` (0.0015, that value included) added since the last ink photo of this hold, or outside a hold since the reference (the board as last accepted). It calls `note_ink()` (blank, start or extend the hold) and becomes the last ink photo, so noise during a hold never extends it.
  - **Wiped:** during a hold, the board back within `ink_min_ratio` of the reference (all change, `ink_change`). It calls `note_wiped()`. Never after a calibration or fit change during that hold: the new reference already has the ink, so only the timer ends it.
  - **After a hold:** the board as it is, leftover ink and all, becomes the reference. Wiping that ink later adds none, so it never blanks the view.
  - **Otherwise** the reference stays, so a slow writer's small additions add up, until it's `REFERENCE_MAX_AGE_S` (5 min, a judgment call) old; then it moves to the capture before this report, its age counting from then, so light drift never builds up to ink.
  - The first clean capture, and the first after a calibration or fit change, becomes the reference.
  - The numbers: replaying `added_ink_ratio` over the kept snapshots from 2026-10-20/21 (after the glare fix), noise on an untouched board added 0.0000-0.0004 against the photo before it, and the smallest real marks 0.0029 (one stroke) and 0.0032 (that stroke plus a small X, against the photo before both). Reports from before the glare fix (0.0005-0.0010 for real writing on 2026-10-19) came from the old detector and weren't used.
- `IdleFiles(life_dir, todo_state_path, tasks_path, usage_path, agenda_path, cache_dir, keynotes_path=None)`.
- `IdleHooks(now, monotonic, lookups)`, `Lookups(place, forecast, feed)`: the clocks and network calls, swapped for fakes in tests.
- `add_idle_routes(app, controller)`: `POST /api/idle/show|hide|sync`, behind the daemon's token guard.

## Sources and refresh

| Region | Source | Refresh |
|---|---|---|
| Clock, date | the page's own clock (`static/idle/clock.js`) | each minute boundary |
| Today, priorities, upcoming (plan side) | this and next week's `plan.md`, `.state/todo.json` (read-only) | `local_sources.py`: every 15 s, read only when an mtime, the date or a 5-minute bucket changed |
| Keynotes | `.state/keynotes.json` (read-only, today's only; `whiteboard.keynotes`) | same |
| Upcoming (calendar side) | `tools/calendar/.state/agenda.json` (read-only) | same |
| Agents, usage line | `tools/console/.state/tasks.json`, `tools/usage/.state/usage.json` | same |
| Weather | `signal_weather` (Open-Meteo, keyless, °F) for the PC's place | `network.py`: every `[idle] weather_min` (30), cache in `.state/idle/weather.json`, stale fallback up to 6 h |
| Place | IP lookup (`signal_weather.locate`, ipapi.co) at start and every `[idle] locate_hours` (6); else the last place found, else `[idle] place/lat/lon` (Springfield, IL) | `.state/idle/location.json` |
| News | `[idle] news_feed` (default AllSides, RSS 2.0 or Atom), its top 6 fresh titles, labelled `[idle] news_source`, scrolling at `[idle] ticker_px_s` | every `[idle] news_min` (30), in memory, last headlines kept up to 6 h |

Network fetches run as background tasks with 4 s timeouts, so they never hold up the loop or the page. A failing source keeps its last data and logs once at INFO when it fails and once when it's back (`outages.py`); nothing raises out of the loop.

## Depends on

`whiteboard.idle`, `whiteboard.todo`, `whiteboard.keynotes`, `whiteboard.display` (scene views, `BoardController`), `whiteboard.config`, `signal_weather`, `signal_tasks`, `signal_jsonstate`, `aiohttp`.
