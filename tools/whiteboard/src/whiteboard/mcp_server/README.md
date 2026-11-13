# whiteboard.mcp_server

The stdio MCP server behind `whiteboard mcp` (server name `whiteboard`, `mcp==2.3.0`). Each tool is a thin call to the daemon's HTTP API, run in a worker thread. Logs go to stderr only.

## Tools

| Tool | What it does |
|------|--------------|
| `board_look(clean=True, raw=False)` | Photo of the board as MCP image content, plus a line with its size, the coordinate space and the projected items. `raw` skips the board fit, for reading corners. |
| `board_draw(kind, content, x, y, w, h, id="", style={})` | Project an item (svg, mermaid, text, markdown, math, rough, image). Returns its id. |
| `board_move(id, x, y, w, h)` | Move or resize an item. |
| `board_remove(id)`, `board_clear()`, `board_list()` | Remove one, remove all, list. |
| `board_highlight(x, y, w, h, seconds=3)` | Flash a bright box. |
| `board_placeholder(x, y, w, h)` | Move this turn's "Claude is thinking" box to where you'll draw. |
| `board_calibrate()` | ArUco calibration, then auto-fit the board outline. |
| `board_fit(mode="auto", quad=None)` | Re-detect (`auto`), show the outline (`show`), `clear`, or set 8 corner numbers by hand. |
| `board_realign()` | Flash the markers and re-align if the projector, camera or board moved; returns what changed and the numbers. |
| `board_save(name, description="", overwrite=False, refresher=None)` | Save the board: the projected items, plus a photo and the owner's extracted ink when calibrated. Refuses a taken name without `overwrite`. `refresher` (`tasks` or `todo`) marks a board drawn from live data, for the console's Update button. |
| `board_load(name, mode="replace", include_ink=True)` | Bring a save back (`replace` or `overlay`), with the saved ink projected over the board. |
| `board_saves()`, `board_delete_save(name)` | List saves (newest first, with descriptions, to find an old diagram), delete one. |
| `board_todo_show()`, `board_todo_hide()` | Switch to the TODO view (synced from `life/` first) and back to the items, which are kept as they were. |
| `board_todo_sync()` | Re-read `life/` and update the TODO view without switching. Returns counts and every item with its id. |
| `board_todo_done(item)`, `board_todo_undone(item)` | Tick or untick an item (id or a unique piece of its text) in this or next week's plan, then update the view. |
| `board_tasks_show()` | Clear the board and draw the task grid from the console's task list and the usage file (see `whiteboard.tasks_grid`). Returns the counts only. |
| `board_idle_show()`, `board_idle_hide()` | The idle view, the board's default when nothing is drawn, and back to the items. Returns the view and counts only (no plan or feed text). |
| `board_night_show(sky=True)`, `board_night_hide()` | Sleep mode's night view (tonight's dim sky, or black) and back to the view it hid. Sleep mode calls the daemon itself; these are for when the owner asks. While it shows, drawings stay hidden and flashes are refused. |

The `board_todo_*` results (except hide) come back as JSON inside `<untrusted_plan_content>` tags, after a line saying that item text is the owner's plan data, some of it copied from email, and never instructions. Every `<` in the JSON is escaped, so plan text can't close the frame (`whiteboard.todo.plan_data`). A `board_todo_*` error can quote plan lines, so it comes back framed the same way, as `{"ok": false, "error": ...}`.

The descriptions (descriptions.py) cover three things. Coordinates are board pixels: 1280x720 projector pixels without a fit, or the logical board size once fitted, the same space as `board_look`. The page is black, so drawings need bright colours and no large fills. Additions go in empty space next to the owner's ink.

The board agent auto-allows every `mcp__whiteboard__` tool except `board_todo_done` and `board_todo_undone`, which write `life/`, and `board_night_show` and `board_night_hide`, which belong to sleep mode (hiding the night view lights up the room while the owner sleeps). The board is untrusted, so those ask the owner first.

The daemon is found through `.state/daemon.json` and `.state/token`. The first tool call starts it detached if it isn't running, so merely loading `.mcp.json` never lights the projector.

## Public API

`SERVER_NAME`, `BoardTools(connection)`, `build_server(tools)`, `run_stdio_server(settings, config_path)`.

## Register it

In the repo root's `.mcp.json`. The key must be `whiteboard`, because it sets the `mcp__whiteboard__` prefix the board agent auto-allows:

```json
"whiteboard": {
  "command": "uv",
  "args": ["run", "--project", "tools/whiteboard", "--frozen", "whiteboard", "mcp"]
}
```

## Depends on

`mcp`, `whiteboard.config`, `whiteboard.daemon_client`, `whiteboard.display.scene` (`LOADING_ID`, `TODO_VIEW`), `whiteboard.todo` (`plan_data`, `PLAN_DATA_OPEN`).
