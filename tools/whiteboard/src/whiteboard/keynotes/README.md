# whiteboard.keynotes

The day's keynotes: 2-4 short lines on the idle and TODO views saying what matters most today and why. A model writes them once a morning; plain code shows them.

## Public API

- `generate_keynotes(life_dir, today, (todo_state_path, keynotes_path), ask=None)`: reads this and next week's plans the way the TODO view groups them (`todo.build_groups`, items ticked before today left out using `.state/todo.json`), plus the week's first priorities, and asks `MODEL` ("sonnet", the latest Sonnet) through `agent.ask_sdk`: one turn, no tools, no settings files. The plan data goes in the `todo.plan_data` frame and the system prompt says it's data, never instructions. The reply must be `{"lines": [...]}`; anything else raises `KeynotesError` and leaves the old file alone. Times out after 180 s.
- `read_keynotes(path, today)`: the lines, or `()` when the file is missing, unreadable, malformed or written for another day. Never raises. Lines are cleaned (`idle.clean_text`) and capped at `MAX_LINES` (4) and 80 characters.
- `write_keynotes(path, day, lines, model)`, `parse_lines(text)`, `KEYNOTES_FILE` (`keynotes.json` in `.state/`).

File: `{"date", "generated_at", "model", "lines"}`.

## Who uses it

- `whiteboard keynotes` (cli/commands/views/keynotes.py) generates now and refreshes a running daemon. The 06:00 scheduled task runs it before the TODO sync (`schedule/`).
- The idle view's KEYNOTES region (in PRIORITIES' place on days that have keynotes) and the TODO view's block under its header (`todo.layout_todo(..., keynotes)`).

## Depends on

`whiteboard.todo`, `whiteboard.idle` (`read_priorities`, `clean_text`), `whiteboard.agent` (`ask_sdk`, `stream_message`), `whiteboard.shared`.
