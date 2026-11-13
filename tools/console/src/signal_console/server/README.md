# server

The console's aiohttp server on 127.0.0.1. `serve(port, state_dir, web_dir)` runs it, and `build_app(services, web_dir)` builds it, which is what tests use.

- `events.py`: `EventHub` fans events out to SSE listeners and keeps the last 200 message, delivery, voice and note events in `.state/history.jsonl`.
- `dispatch.py`: `Dispatcher.submit(request)` emits a typed "you" message, sends it to the claimed inbox in the background, then emits exactly one `delivery` event (`sent`, or `failed` with a generic error if something unexpected breaks).
- `action_runner.py`: `ActionRunner.submit(plan)` runs a button directly (no orchestrator): it emits the "you" action message and a `delivery` `running`, runs the plan's step in the background (`signal_console.actions`), then emits exactly one `delivery` `done` with `result` (what happened, in words) or `failed` with `error`, and refreshes the status (forcing a whiteboard read after a board action, which the throttled refresh would skip). One action per lock (`voice`, `board`) at a time; another raises `ActionBusy`.
- `hub_feed.py`: `HubFeed` tails `hub.log` for the hub's phase and `voice` events, drops speech the hub ignored (no wake phrase) and repeats of one error within 30 s.
- `watcher.py`: `StatusWatcher` polls the claim, the hub (a live hub not listening yet reads as `starting`) and the whiteboard, reads `hub.log` through `HubFeed`, keeps the orchestrator's turn state (`record_turn`, plus the session's agents from `usage.json`), publishes `state` when anything changes, and a `note` when the claim changes.
- `tasks_feed.py`: `TasksFeed` polls the mtimes of `.state/tasks.json` and tools/usage's `usage.json` at 1 Hz (rebuilding every 30 s anyway, for windows that reset) and publishes a `tasks` event when the Tasks page's data changes: `{updatedAt, active, queued, done, needsYou, overallPct, usage}`, in display order. Live only; a new stream gets `current()` first.
- `services.py`: the `Services` the routes use, kept under `SERVICES_KEY`.
- `security/`: the request guard, the security headers and the page login.
- `routes/`: the `/api/*` routes, the SSE route, the devices and away routes, the camera proxy, the local routes, and the static files.

API: `POST /api/login {key}` -> `{token}`. With `X-Console-Token: <token>`: `GET /api/state`, `GET /api/events` (SSE, read with a streaming `fetch`: `state`, `tasks`, `message`, `delivery`, `voice`, `note`), `POST /api/send {text}`, `POST /api/action {action, args?}` (202, 400 for a bad action or save name, 409 while one with the same lock runs), `GET /api/devices` (`{devices: [row], away}`), `POST /api/away {on, until?}` and `GET /api/camera/stream` (the webcam's MJPEG, proxied). Event shapes and the dedupe rule are in `routes/stream.py`'s docstring. The local routes, with `X-Console-Key`, are `POST /api/hook/turn {phase, session_id, at, background_tasks?, text?}` and `POST /api/local/login-key`.

Public API: `signal_console.server`. Depends on `aiohttp`, `actions`, `orchestrator`, `status`, `hub`, `turns`, `away`, `state_files`, `signal_tasks` and `signal_brief`.
