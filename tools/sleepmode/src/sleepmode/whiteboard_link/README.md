# sleepmode.whiteboard_link

sleepmode's side of the whiteboard night view contract. The contract itself is in `tools/sleepmode/README.md`.

## Public API

- `NightViewClient(state_dir, timeout_s=5.0)`:
  - `show(seed, sky)` sends `POST /api/night/show {"seed", "sky"}`.
  - `hide()` sends `POST /api/night/hide {}`.
  - `is_showing()` sends `GET /api/status` and is true when `view` is `"night"` and `pages_connected` is above 0 (the kiosk shows it).
  - Each reads the whiteboard's `.state/daemon.json` (port) and `.state/token` on each call, send `X-Signal-Token`, and bypass proxies.
  - A `daemon.json` without a running `pid` fails at once, without trying its port.
  - Every failure raises `WhiteboardUnavailableError` with a readable reason: not running, not answering, no such route yet (404), another HTTP error, or a reply without `"ok": true`.
- `night_seed(now) -> int`: `YYYYMMDD` of the evening the night began (noon to noon), so the sky is new each night and the same if shown twice in one night.

The client never starts the whiteboard daemon. That's:

- `start_whiteboard_if_down(state_dir, whiteboard_root) -> bool`: unless `daemon.json` names a live pid, runs `uv run --project tools/whiteboard --frozen whiteboard serve` detached (no window, output appended to the whiteboard's `.state/daemon.log`, which moves to `daemon.log.1` first past 5 MB) and returns at once, True if it started one. It runs the whiteboard's own CLI, never its code, so both tools stay standalone. Raises `OSError` if the start fails. Sleep calls it when the night view can't be shown; the daemon then shows the night view by itself.

- `read_live_daemon_info(state_dir) -> dict | None` (in `discovery.py`): `daemon.json`'s contents if it names a running pid, else None. Both of the above use it.

## Depends on

`sleepmode.shared` (`is_process_alive`, `popen_detached`), the standard library (`urllib`, `json`, `subprocess`) and `uv` on `PATH`.
