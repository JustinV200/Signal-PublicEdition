# empty

`EmptyState` is the one empty state of Chat, Voice, Boards and Tasks: `ui`'s dashed-ring `Mark` one text row tall in `--fg-2`, a `.hud-label` naming what is missing (`label`, sentence case; the HUD style capitalises it) and its children under the label in `--fg-2` (one line; Chat adds its claim help there). The label carries the meaning, the ring only repeats it.

| View   | Label                 | Line                                                                               |
| ------ | --------------------- | ---------------------------------------------------------------------------------- |
| Chat   | `NO MESSAGES YET`     | which session is linked and how to send, or the claim help; then where the rest is |
| Voice  | `NOTHING HEARD YET`   | `When Voice hears or says something, it shows here.`                               |
| Boards | `NO SAVED BOARDS`     | `Ask Claude to save a board and it's listed here.`                                 |
| Tasks  | `NOTHING IN PROGRESS` | `No tasks right now. Claude lists its work here when it starts some.`              |

Public API: `index.ts`. Depends on React and `ui` (`Mark`).
