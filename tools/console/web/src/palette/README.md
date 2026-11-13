# palette

Command mode (Ctrl+K). `buildCommands` lists the fixed commands for the current state (`voice start|stop`, `board load <name>` per save, `board todo` and `board idle` when the whiteboard has a view, `view …`, `theme …`), `filterCommands` does the substring match (8 at most), and `Palette` draws the matches above the input line. The input line owns the query and the keys.

Public API: `index.ts`. Depends on `api` (types) and `state` (types).
