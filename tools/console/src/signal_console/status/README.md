# status

Read-only views of the other tools. Nothing here starts or changes anything.

- `voice.py`: `is_hub_listening()` checks audiohub's token file, then tries a TCP connect to 127.0.0.1:8765 (0.5 s).
- `hub_log.py`: `parse_hub_line(line)` turns a `[HH:MM:SS.t] label: detail` status line into a `HubLine(phase, kind, text)`.
- `log_tail.py`: `LogTail` returns the complete new lines of `hub.log` on each call.
- `boards.py`: `read_board_status(session)` gets the whiteboard's saves, view and item count from its daemon, and returns an empty status when the daemon is down. In `/api/state` it is `board: {saves: [{name, updatedAt, description, refresher}], view, itemCount, online}`; `description` is null unless the save has a non-empty one, `refresher` is `tasks`, `todo` or null (the boards view's `Show live version` button), `view` is passed through as the daemon names it (`items`, `todo`, `idle`, or `night` under sleep mode's night view; never a save name), `itemCount` is the daemon's `item_count` (null when an older build sends none; 0 tells the page an `items` view is empty, so a load over it does not ask first), and `online` is false when the daemon didn't answer (then there are no saves and no view).
- `whiteboard_api.py`: `find_whiteboard()` reads the daemon's port and token (`WhiteboardTarget`, whose repr hides the token) and `get_whiteboard_json(session, target, path)` asks it for JSON with the `X-Signal-Token` header. The boards reader, the devices rows and the camera proxy share it; `WHITEBOARD_DAEMON_FILE` (the daemon's `daemon.json`) is also read by the health checks.
- `devices.py`: `DeviceReader.rows(voice)` builds the Connected devices rows `{id, name, state: on|off|unknown, words}` (the webcam's adds `canOpen`): the projector and webcam from one whiteboard `/api/status`, Voice from the watcher's voice state, and the desktop browser and Docker from a process scan cached 10 s.
- `local_processes.py`: `scan_processes(profile)`: is an `msedge.exe` on tools/browser's profile running, and is Docker Desktop's backend.

Public API: `signal_console.status`. Depends on `aiohttp`, `psutil`, `paths` and `state_files`.
