# state/actions

The life of a request the page sends (a typed message or a button's action), inside the `state` package.

- `sending.ts`: optimistic send for text and actions; `[retry]` re-sends the origin as a new message.
- `actionLabels.ts`: placeholder text for an action row and the confirm prompt.
- `actionProgress.ts`: where a sent action has got to, read off its `delivery` (`sending`, `working` while the server runs it, `done`, `failed`; `sent` only for replayed rows from before buttons ran in the server); and which rows and action names are still pending (local origin only, capped at `PENDING_MAX_MS`), shared by the buttons and the scope.
- `usePendingActions.ts`: binds the pending set to the store for the buttons, ticking so the cap can lift a wedged one.

Entry point: `index.ts` (re-exported by `state/index.ts`). Depends on `api`, `time` and the `state` reducer and store.
