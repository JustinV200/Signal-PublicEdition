# static/idle

The idle view's page side: draws the daemon's idle payload (see `whiteboard/idle/README.md`) into `#idle`. Lifted from the approved mock in `refdocs/research/idle-board/` (design.md has the grid, type scale and colour roles).

- `idle.js` (entry): `renderIdle(data)` builds the board at the design size, 1112x720; `fitIdle(stage)` scales it onto the stage, centred. A region whose data changed fades in once; a task that turned done since the last render gets the TODO view's cross-out animation (`todo.css` keyframes).
- `clock.js`: the dial, `HH:MM` (no seconds) and the date, from the PC's clock, updated on each minute boundary. The daemon counts each boundary as a page change for the camera (`display/server/board/minute.py`).
- `regions.js`: today (its overdue count from the payload's `overdue`), keynotes (in the priorities' box on a day that has them) or priorities, agents, upcoming and the news footer, with their "+N more" and empty states.
- `ticker.js`: the news footer's headlines scrolling right to left (TV style) at the payload's `px_s`, as a conveyor: appended at the right, dropped at the left, new headlines joining at the loop seam, so it never jumps. Its frame loop runs only while it's shown and moving; hidden (another view, the night sky, a blank flash) or still (`prefers-reduced-motion`), it stops and checks again once a second. The camera's motion check leaves its band out (`display/server/board/idle_ticker.py`).
- `weather.js`: the weather block and its line glyphs (built with `createElementNS`, no markup strings).
- `parts.js`: shared pieces; `fitTexts` cuts an overflowing row at its first `:`, `;` or ` (` that leaves at least 8 characters, before the ellipsis.
- `layout.js`: the grid, slots and colour roles. Course chip names and colours come in the payload.
- `idle.css` (variables and regions), `top.css` (the dial, clock, date and weather) and `ticker.css` (the news ticker): every rule scoped to `.idle-board`.

Every string goes in with `textContent`. Nothing is filled: the page is projected, and black is no light. Colours always come with a word or number (the owner is colourblind).
