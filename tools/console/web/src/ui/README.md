# ui

Shared controls. `Button` is the console's one button: a `--border`-outlined box in the small type with hover, press and focus states, an optional shortcut hint, a `pending` state that reads "Working…" and ignores clicks, and `disabledReason`, which disables it and shows the reason as a tooltip and an `--fg-2` caption beside it. `quietReason` disables it with the reason as a tooltip only (no caption, so nothing shifts; Send, and both night-view buttons on Boards), and `awaitsInput` keeps a disabled button's border solid while it only waits for typing (Send with an empty draft). `primary` adds the accent outline, the `--accent-fill` resting fill and a 600 label. Tabs (`status`) and list rows (`views/boards`) have their own looks; everything else clickable uses `Button`.

`Mark` draws the console's state shapes (`disc`, `ring`, `dashedRing` (nothing here yet: the `empty` state), `half`, `square`, `diamond`, `triangle`, `cross`, `check`) as inline SVG in `currentColor`, since the bundled Plex subset has none of `● ○ ◐ ▸ ✗ ✓` and they fell back to other fonts. `MarkPath` draws the same shape inside another SVG (the scope). Marks are hidden from screen readers: a word beside them always carries the state.

`CopyButton` is the console's one copy-to-clipboard control (`text`, and optionally `label`, a `note` shown before any click and a `copiedNote` after one): a `Button` with a note beside it that says how the copy went (`role="status"`). It writes with `navigator.clipboard.writeText`; when that is missing, throws or is refused (it is not verified in the Edge app window on `http://127.0.0.1`), it shows the text in a read-only box, focused and selected, and says to press Ctrl+C. Chat's claim sentence, the setup wizard's `Copy for Claude` and the open command (signed-out page, server-down notice, Help) use it.

`OpenCommand` is the `console open` line built on it: a lead, the command in inline code, then Copy (`Copied. Paste it into a terminal.`). It takes the server's own full line (`state`'s `openCommand`, with this checkout's absolute path); before the page has heard it, the repo-relative `uv run --project tools/console --frozen --no-sync console open`, marked as run from the repo's root folder. The signed-out page, the server-down notice and Help use it.

`usePageVisible` tells whether the page is visible, so animations and polls can stop while it's hidden; `isPageVisible` is the same check read once (`scroll` marks rows seen only while it is true).

Public API: `index.ts`. Depends on React only.
