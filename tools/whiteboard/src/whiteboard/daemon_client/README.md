# whiteboard.daemon_client

How the MCP server and the CLI reach the daemon. It's kept apart from `whiteboard.daemon` so clients don't import OpenCV, the camera or the aiohttp server just to send a request.

## Public API

- `DaemonConnection(location, is_auto_start=True)` (with False, no daemon means `DaemonStartError`)
  - `.call(lambda api: api.look(True))` finds the daemon. If none answers, it starts one detached (`python -m whiteboard.cli serve`, `DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP | CREATE_BREAKAWAY_FROM_JOB` so the caller's job closing doesn't kill it, retried without breakaway if the job forbids it; output in `.state/daemon.log`, moved to `daemon.log.1` first when over 5 MB) and waits up to 45 s for `/api/status`.
  - If the daemon went away since the last call, it reconnects and retries once.
  - On a 403 (`DaemonAuthError`: the daemon restarted with a new token or port) it re-reads `daemon.json` and `token` and retries once, but only if either changed. Otherwise it raises, so it never loops. A restart that left no daemon raises `DaemonAuthError` too; the next unreachable call starts one.
- `DaemonLocation(state_dir, port, config_path=None)`, `find_daemon(location)`.
- `DaemonApi(base_url, token)`: blocking urllib client with system proxies off. It sends `X-Signal-Token` on every request.
  - Methods: `status`, `has_same_target`, `scene`, `put_item`, `patch_item`, `delete_item`, `clear`, `highlight`, `look(clean, raw)`, `calibrate`, `fit_quad`, `fit_auto`, `fit_show`, `save_board`, `list_saves`, `load_board`, `delete_save`, `todo(action, item=None)`, `idle(action)`, `night(action, sky=True)`, `shutdown`, and `open_camera_stream()` (the open MJPEG response; close it to end the stream).
  - Raises `DaemonUnreachableError` (nothing listening, safe to retry), `DaemonAuthError` (403, a `DaemonApiError` subclass; also safe to retry) or `DaemonApiError` (other error status or timeout).
- `iter_jpeg_parts(stream)`: the JPEG bytes of each part of that stream, read by `Content-Length`. Raises `DaemonApiError` on a bad or oversized length.
- `send_fit(api, mode, quad)`, `quad_from_numbers(numbers)`, `FIT_MODES`: the fit request shared by `whiteboard fit` and `board_fit`.
- State files in `.state/`: `write_daemon_info` / `read_daemon_info` / `remove_daemon_info` (`daemon.json`), `create_token` / `read_token` (`token`), and `LOG_FILE`.

## Depends on

The standard library only.
