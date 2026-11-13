# whiteboard.display.server.board

The object that owns the live board. Its full API is listed in [../README.md](../README.md); other code imports it from `whiteboard.display.server`.

## Files

- `scene_board.py`: `SceneBoard`, the scene side. Items, the board fit and the view (items, TODO, idle, or the night view on top), each change applied with a pure scene op, saved to `scene.json`, then broadcast over the hub.
- `controller.py`: `BoardController(SceneBoard)`, what the page shows on top of the scene: the display mode and markers, highlights, the TODO and idle views' data (`set_todo`, `set_idle`, `idle_message`), `page_changed_s()` for the camera (each minute boundary counts while the idle view shows: `minute.py`), and the night view's guard (every mode but `normal` and every highlight raise `NightViewError` while it shows).
- `minute.py`: `last_minute_boundary_s(monotonic_now, wall_now)`.
- `modes.py`: `DISPLAY_MODES`, `Marker` and `Highlight`.

## Public API (`__init__.py`)

`BoardController`, `DISPLAY_MODES`, `Marker`, `Highlight`.

## Depends on

`whiteboard.display.scene`, and the server's `hub.py` (`BroadcastHub`).
