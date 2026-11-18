# whiteboard.cli

The `whiteboard` command (`whiteboard.cli.main:main`). `python -m whiteboard.cli` works too, and that's how the daemon gets started detached.

## Commands

| Command | What it does |
|---------|--------------|
| `serve` | Run the daemon in this terminal until Ctrl+C. |
| `stop` | Stop a running daemon cleanly. |
| `status` | Say whether a daemon answers, never starting one: the last line is one JSON object `{words, fix, command}` (the setup tool's health check). Not running passes; exit 1 only when a daemon answers with an error (a stale token) or hangs. |
| `mcp` | Stdio MCP server (for `.mcp.json`). |
| `calibrate` | Marker calibration, then auto-fit the board outline. |
| `fit [auto\|show\|clear] [--quad X1,Y1,...,X4,Y4]` | Re-detect, show or clear the board fit, or set corners by hand. |
| `align` | Measure how far the board has drifted from the fit, in camera px. Doesn't re-align. |
| `realign` | Flash the markers (about 1 s) and re-align if the camera, projector or board moved. Prints what changed. |
| `look [--raw] [--projection]` | Take a snapshot and print its path. |
| `draw KIND CONTENT --x --y --w --h [--id] [--color]` | Project one item. |
| `clear` | Remove every projected item. |
| `save NAME [--description TEXT] [--overwrite]` | Save the board: the projected items, plus a photo and your extracted ink when calibrated. |
| `load NAME [--overlay] [--no-ink]` | Bring a saved board back, replacing the current items unless `--overlay`. |
| `saves` | List saved boards, newest first. |
| `delete-save NAME` | Delete a saved board. |
| `todo sync\|show\|hide [--if-running]` | Refresh the TODO view from `life/`, switch to it, or back to the items. `--if-running` does nothing (exit 0) when no daemon runs, instead of starting one: the 06:00 scheduled task uses it. |
| `todo done\|undone ITEM` | Tick or untick an item (id or a unique piece of its text) in its week plan. |
| `keynotes` | Ask Claude (Sonnet) for today's 2-4 keynote lines from the week plans, save them to `.state/keynotes.json`, print them, and refresh a running daemon (never starts one). The 06:00 scheduled task runs it first. |
| `idle show\|hide\|sync` | The idle view (clock, tasks, weather, agents, upcoming, a headline): show it now, back to the items (on an empty board it returns after `[idle] empty_s`), or re-read every source now. Prints the view and counts. |
| `night show` / `night hide` | Sleep mode's night view: tonight's dim sky, and back to the view it hid. Sleep mode calls the daemon itself; this is for trying it by hand. |
| `camera view` | Watch the webcam live (raw, about 5 fps) in a window, to aim it. q, Esc or closing the window ends it. Uses the daemon's stream, so the daemon can keep the camera. |
| `displays` | List monitors and mark the projector. |
| `cameras` | List webcams. Stop the daemon first, because it holds the camera. |

`--config PATH` works before or after the command. Board commands start the daemon if it isn't running. Errors you can fix (bad config, daemon refused or won't start) print one line and exit 2.

To add a command, define a `Command` in `cli/commands/<module>.py` and add it to `COMMANDS` in `cli/commands/__init__.py`. The commands that switch or redraw what the board shows (`todo`, `idle`, `tasks`, `night`) live in `cli/commands/views/` (see its README).

## Depends on

`whiteboard.config` and `whiteboard.daemon_client`. Each command imports what it needs inside `run()`, so startup stays fast: `daemon`, `mcp_server`, `display.screen` and `camera`.
