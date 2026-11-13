# whiteboard.tasks_grid

The task grid, drawn from the console's task list (`tools/console/.state/tasks.json`, written by `console tasks set`) and tools/usage's `usage.json`, both read through `signal_tasks`. This is the "whiteboard-task-grid" layout coded once.

- `layout.py`: `plan_grid(active_count) -> GridPlan(active, queued, done, hidden)`. Up to 7 active tasks: 3 columns of 340 px boxes; more: 4 columns of 255 px. The queued and done boxes always take the last slots (sharing the bottom row at 8 active, single boxes at 9-10). Past 10 active tasks the least finished are left off and the header says how many. Design pixels are a 1114x720 board.
- `items.py`: `grid_items(groups, usage, now)` builds the items: one `rough` item (`agents`) with every outline, one text per box (name and %, status word, `YOU:` when it needs the owner, next step), one `svg` item (`nums`) holding only the bold white status numbers, the header (`Signal main session:`, counts, overall %, the number key), the queued box worded like the console page (`Queued: 6 tasks, none started`) and the usage line (5-hour and weekly %, agents, its age). `scale_items` maps them onto the real board size. Colour is never the only cue: every box has its number, and the header gives the key.
- `draw.py`: `draw_task_grid(api, tasks_path, usage_path, now)` hides the to-do view if it's up, clears the board, draws every item and returns a one-line summary. It never loads a save, so there's no stale snapshot or ghost ink.

Depends on `signal_tasks`, `whiteboard.daemon_client` and `whiteboard.display.scene`.
