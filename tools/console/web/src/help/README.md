# help

`HelpPanel` is the block that opens above the view from the status line's Help button (`helpOpen` in the store): what Scope, Chat, Voice and Boards do, that typed messages go to Claude while buttons run at once in the console, and the shortcuts. Esc or its Close button closes it. Its view list (`VIEW_HELP`) also drives `TourBar`, the console tour the setup wizard starts: one view at a time, switching to it, with Back, Next and End tour (`tourStep` in the store).

Public API: `index.ts`. Depends on `state` and `ui`.
