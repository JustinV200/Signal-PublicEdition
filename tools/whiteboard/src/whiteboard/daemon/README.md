# whiteboard.daemon

The `whiteboard serve` process. It wires display, camera and agent together in one asyncio loop.

## Public API

- `run_daemon(settings, state_dir=STATE_DIR)` runs until Ctrl+C or `POST /api/shutdown` (`whiteboard stop`).

## What it does

1. Claims `127.0.0.1:<port>` exclusively first, so a second `serve` exits before touching anything. Then it writes a fresh API token to `.state/token` (owner-only ACL), finds the projector (`[display] name_match`, else the non-primary display), loads the scene and syncs the TODO view from `life/`.
2. Opens the camera in a thread. If the camera fails, drawing still works; look, calibrate and the watcher are off.
3. Builds display's app with the camera hooks (`/api/look`, `/api/calibrate`, status). It adds its own routes (`/api/look/raw`, `/api/fit/auto`, `/api/fit/show`, `/api/align/check`, `/api/align/realign`, `/api/shutdown`, `/api/kiosk/open`), the saved-board routes, the `/api/todo` and `/api/idle` routes, `GET /api/camera/stream` and the request guard.
4. Serves on the claimed socket (no access log: it leaked the kiosk's `?token=` URL and buried the log) and writes `.state/daemon.json` (`pid`, `port`).
5. If tools/sleepmode's `.state/state.json` says asleep and the scene isn't already on the night view, switches to it (that night's seed, `night_resume.py`), so a daemon started mid-night never lights the board. Then starts the kiosk's watchdog, which opens the Edge kiosk on the projector and reopens it whenever no board page is connected (see [kiosk/README.md](kiosk/README.md)), then starts the change watcher, the board agent and the drift monitor if `[watcher]` / `[agent]` / `[align] auto` enable them. The drift monitor needs the watcher. The capture rig gets `BoardController.page_changed_s`, so the watcher settles after every blank, marker flash and drawing the daemon makes, wherever it came from. While the night view (sleep mode) shows, that's `math.inf`: the watcher takes no photos, so the agent and the cross-out check get nothing, and the drift monitor runs no checks or marker flashes. The board refuses any flash meanwhile, so a clean look, calibrate, `fit auto`, `fit show`, align and re-align answer 409 (see `display/server`); a look with `clean=false` and a fit set by hand still work. Every change first goes to the idle view's `InkWatch` (new ink blanks the idle view; see idle/README.md). With the agent on, it then passes the TODO view's cross-out check (`StrikeWatcher`) before the agent; with it off, there's no check and no model call.
6. On the way out it unwinds in reverse: drift monitor, watcher, agent, kiosk watchdog, kiosk, `daemon.json`, the stop event (ends camera streams), HTTP server, camera.

## Security (request_guard.py)

Any web page can send requests to 127.0.0.1. So every `/api/*` request needs the `X-Signal-Token` header, compared with `hmac.compare_digest`, and an `Origin` header (if present) must be the daemon's own. `/ws` must come from `http://127.0.0.1:<port>` or `http://localhost:<port>`. `/board` and static files stay open. Display's own middleware also rejects non-loopback `Host` headers.

## Camera stream (camera_stream.py)

`GET /api/camera/stream` (`whiteboard camera view`) sends the raw webcam view as `multipart/x-mixed-replace` JPEGs: about 5 fps (`FRAME_INTERVAL_S`), at most 960 px wide, quality 70. Each part carries a `Content-Length`.

- It re-encodes `Camera.latest()`, the frame the grab thread already keeps, so it never opens the camera and the watcher sees no difference. It never changes the page (no blank, markers or rectification).
- 503 without a camera or a live frame, 429 past `MAX_STREAMS` (2). It's behind the request guard like every `/api/` route.
- A stream ends when a write fails (the viewer left), the camera stops delivering, or the stop event is set. `run_daemon` sets that event as it unwinds, before the HTTP server's cleanup, so Ctrl+C doesn't wait on open streams.
- A future console "Connected devices" page will proxy it with the token, so no browser holds the token.

## Saved boards (save_routes.py)

| Route | Body / result |
|---|---|
| `GET /api/saves` | `{ok, saves: [meta]}`, newest first |
| `POST /api/saves` | `{name, description?, overwrite?}` → the meta, `folder`, and a `note` when only the items were saved (no camera, not calibrated, or the night view showing) |
| `POST /api/saves/load` | `{name, mode?: replace\|overlay, include_ink?}` → `{name, slug, mode, item_count, ink_projected, scaled, dropped_missing_images}` |
| `POST /api/saves/delete` | `{name}` → `{ok, deleted: meta}`; 404 if unknown |

A save's photo is one clean capture through `grab_clean_frame`, under the rig's capture lock. Folders live in `.state/boards/` (see `whiteboard.saves`).

## Idle view (idle/)

`IdleController` and the `/api/idle` routes: the board's default view when nothing is drawn, kept fresh from `life/`, the task list, usage, the calendar cache, Open-Meteo and a news feed, with no model. See [idle/README.md](idle/README.md). It caches the weather and the place in `.state/idle/`. It starts after the TODO view's first sync and stops before the port is released.

## TODO view (todo/)

`TodoController`, the `/api/todo` routes and the cross-out check. See [todo/README.md](todo/README.md). Its state is `.state/todo.json` (which items were done since when) and `.state/todo.log` (every checkbox it changed in `life/`).

## Board fit

The scene's `board_quad` (in `scene.json`) is the only record of the fit. `calibration.json` keeps the marker calibration alone. `BoardViewSync` combines the two into the calibration the capture rig rectifies with. It does this every time the rig switches page mode. So a fit set by calibration, by `whiteboard fit`, or by a plain `POST /api/fit` reaches `board_look` and the watcher.

Marker tiles are sent to the page as `data:` PNG URLs, so no extra route serves them.

## Automatic re-align (realign/)

One `Realigner` (see [realign/README.md](realign/README.md)) is shared by the drift monitor (after board drift, and every `marker_check_s` while idle) and `POST /api/align/realign` (`whiteboard realign`, `board_realign`). It flashes the markers, solves, and re-aligns only if something moved and every check passed. Its result is `{ok, changed, message, projector_drift_px, camera_shift_px, reprojection_error_px, before_px, after_px}`.

`POST /api/align/check` (`whiteboard align`) measures the photo drift once and never re-aligns: `{ok, error_px, note, detected, expected}` in camera px.

## Depends on

`whiteboard.config`, `whiteboard.display` (scene, server, screen), `whiteboard.camera`, `whiteboard.agent`, `whiteboard.saves`, `whiteboard.todo`, `whiteboard.idle`, `whiteboard.daemon_client`, `signal_weather`, `aiohttp`.
