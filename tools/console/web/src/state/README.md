# state

The console's in-memory state and the lifecycle that feeds it.

- `reducer.ts`: `AppState`, `StoreAction`, `reduce`. Auth, connection, server snapshot, the task list (`tasks` events), messages with local delivery status (console `note` events land here as `note` rows), voice feed, view (`scope` is home; `startState` opens on the view the URL asked for), input mode, boards cursor, help panel, `setupTool` (where the setup wizard opens) and `tourStep` (the console tour), `syncedAt` (when the server last sent anything) and `refreshTick` (bumped by the Refresh button).
- `dedupe.ts`: id-keyed insert that keeps time order and the first event per id (the server replays events on every connect).
- `boards.ts`: board rows (to-do list, idle board, then saves) with the action that puts a row on the projector, whether the to-do list can be requested (off only when the whiteboard is on but reports no view), which row is showing (only the to-do and idle rows can be: `board.view` is `todo`, `idle` or `items`, never a save name) and the words for the view; each row's `updateArgs` (for `board.update`: a save with a refresher, or the to-do list) and the night-view reason that disables Realign and Full calibrate.
- `actions/`: optimistic sending, action row labels, where a sent action has got to and the set still pending (see its README).
- `session.ts`: `takeHashLink` pulls `#k=<key>` (and `&v=<view>&t=<tool>` from `console open --view setup`) out of the URL before render; `startSession` redeems it for a token and fetches the first snapshot; a 401 anywhere is `out`.
- `useConnection.ts`: `checking -> in | out`, the event stream while `in` (resynced on a `refreshTick` change, when the page becomes visible again and on `online`), retry on hashchange/focus while `out`.
- `store.tsx`: `StoreProvider` and `useStore()`.
- `theme.ts`: the dark/light switch, remembered in localStorage.

Public API: `index.ts`. Depends on `api` and `time`.
