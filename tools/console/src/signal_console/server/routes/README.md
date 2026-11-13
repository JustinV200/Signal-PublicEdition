# server/routes

- `api.py`: `/api/login` (key -> session token), `/api/state`, `/api/send` (to the orchestrator) and `/api/action` (checked by `signal_console.actions.plan_action`, run by the server's `ActionRunner`; 409 while the same lock is busy).
- `stream.py`: `/api/events` (SSE). It sends the state, replays the history, then streams live events. Its docstring holds the dedupe rule.
- `devices.py`: `GET /api/devices` (the Connected devices rows and away mode) and `POST /api/away {on, until?}`, the owner's own Away/Here toggle, which acts without the orchestrator.
- `models.py`: `POST /api/models {target, field, index}`, the owner's model or effort pick from the model strip. It also acts directly: `index` points into `/api/state`'s `models.choices`, and only the settings' `model`/`effortLevel` keys or voice's `brain-choice.json` are written (`signal_console.models`). 400 for a bad pick, 409 when the file refuses it (doesn't parse, kept changing).
- `camera.py`: `GET /api/camera/stream`, the whiteboard webcam's MJPEG stream. The server adds the whiteboard's `X-Signal-Token` upstream, so the page never sees it; only the multipart body and its content type cross over. The daemon's 429 (2 viewers) and 503 (no picture) come back as plain words; closing the page's request ends the upstream one.
- `setup.py`: `POST /api/setup/run {command, ...}` runs one setup CLI command (`signal_console.setup_cli`) and streams NDJSON (`{"line"}` per output line, then `{"exit"}`); 400 for a bad request, 409 while another writing command runs. `POST /api/setup/terminal {tool}` opens a terminal on `setup.ps1 <tool>`.
- `local.py`: `/api/hook/turn` (checks the report, keeps a Stop's known `effort`, updates the turn state, shows an end's `text` as Claude's message) and `/api/local/login-key`.
- `static.py`: `web/dist` with SPA fallback, or a placeholder page until the frontend is built. Paths are checked as text before any filesystem call.
- `json_body.py`: `read_json_object` (400 unless the body is a JSON object). The body is read as UTF-8 whatever charset the request names.

Public API: the `add_*_routes` functions in `signal_console.server.routes`. Depends on `aiohttp`, `actions`, `orchestrator`, `away`, `models`, `setup_cli`, `status` and `server.services`.
