# ui

Shared controls. `Button` is the console's one button: a bordered box with hover, press and focus states, an optional shortcut hint, a `pending` state that reads "Working…" and ignores clicks, and `disabledReason`, which disables it and shows the reason as a tooltip and a caption beside it. Tabs (`status`) and list rows (`views/boards`) have their own looks; everything else clickable uses `Button`.

Public API: `index.ts`. Depends on React only.
