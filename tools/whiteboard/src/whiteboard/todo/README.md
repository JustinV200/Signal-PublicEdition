# whiteboard.todo

The TODO view's logic: read the owner's todos from `life/`, decide what the board shows and where, and tell which rows a marker line crosses out. No daemon, camera or web server here; `whiteboard.daemon.todo` wires it to the board.

## Subpackages

- `source/`: find this and next week's `plan.md`, parse their todo lines and due dates, and `set_line_done`, the whiteboard's only write to `life/`. See its README.
- `view/`: group the lines (Overdue, today, tomorrow, this week, of note) with short titles, diff a sync against the last one, lay the view out in board pixels, and build the page's JSON. See its README.
- `strikes.py`: strike geometry. A row is a cross-out candidate when newly added ink covers at least 60% of its text's width in the middle band of the row (20% to 80% of its height). A short item is measured over at least 2 em of its font, so a tick or one letter over "A18" isn't enough. The new ink over the text must also sit near the row's middle (its centre within 0.35 row heights), so a line along the row's edge, a neighbour's cross-out seen through a slightly-off calibration, isn't enough either. Underlines, notes and short marks don't count, and neither does erased ink.
- `plan_frame.py`: `plan_data(data)` puts plan text in front of a model as JSON inside `<untrusted_plan_content>` tags (every `<` escaped, so the text can't close the frame), after a line saying it's data, never instructions. The MCP `board_todo_*` results and the cross-out check's item text both use it.

## Public API (`from whiteboard.todo import ...`)

The most used names from both subpackages (`read_week_entries`, `find_entries`, `set_line_done`, `track`, `build_groups`, `layout_todo`, `build_payload`, `TodoStore`, ...), plus `StrikeTarget`, `StrikeCandidate`, `strike_coverage`, `strike_candidates`, `plan_data` and its `PLAN_DATA_OPEN` / `PLAN_DATA_CLOSE` / `PLAN_DATA_NOTE`.

## Depends on

`numpy` (strikes only), `whiteboard.shared` (`write_atomically`, for the store and plan edits). The standard library otherwise.
