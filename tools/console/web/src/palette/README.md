# palette

Command mode (Ctrl+K), the Commands list.

- `commands.ts`: `buildCommands(ctx)` lists only the commands that apply now, in the buttons' words (the action ones through `state`'s `actionLabel`, so a command reads like the chat row it leaves). Fixed commands first: `Start voice` or `Stop voice` (by whether voice runs), `Send to projector: to-do list` and `Send to projector: idle board` (unless the whiteboard is on with no view), `Realign whiteboard` and `Full calibrate` (unless the night view is on), `Go to Scope` to `Go to System` and `Open setup` (less the open view), `Light theme` or `Dark theme` (the other one), `I'm away` or `I'm back` (by away mode; neither while asleep or unknown), `Help`, `Refresh` (the status line's, which shows there only when stale or offline). Saved boards last: `Send to projector: "lecture"`.
- `filter.ts`: `filterCommands(commands, query)` keeps the commands whose label holds every typed word, in any order, ignoring case and `'`, `"` and `-`.
- `Palette.tsx`: the listbox above the input line, 8 rows high (`VISIBLE_ROWS`), scrolling to keep the selected row in view, with `+ 11 more: keep typing` under it while more match; the `▸` (`ui`'s triangle mark) in the input's glyph column and each label on the typed text's column. `PALETTE_LIST_ID` and `paletteOptionId(index)` are for the input's `aria-controls` and `aria-activedescendant`.
- `useCommands.ts`: `useCommands(isOpen)` builds the list from the store while Commands is open: actions go through the confirm gate, so the palette asks exactly what the buttons ask.
- `toggleAway.ts`: `I'm away` / `I'm back` post `/api/away` like System's YOU buttons (the default 3 days); a failure becomes a console note in Chat.

The input line owns the query, the selection and the keys, and is the combobox.

Public API: `index.ts`. Depends on `api` (types and `setAway`), `state` (store, confirm gate, labels, theme) and `ui` (the mark).
