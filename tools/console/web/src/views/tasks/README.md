# views/tasks

The Tasks page (`Ctrl+5`): the task list Claude reports with `console tasks set`, read from the `tasks` SSE event (`state.tasks`). Read only; nothing here sends a request.

- `TasksView.tsx`: header `TASKS  4 active · 1 needs you · overall 58%` with the usage line on the right, the active rows (those that need the owner first, then the server's order: most finished first), then `Queued: N tasks, none started` and `Done today: N` with their names. Empty: the shared `empty` state, `NOTHING IN PROGRESS` and `No tasks right now. Claude lists its work here when it starts some.`
- `DoneGroup.tsx`: `Done today: N`; shows 6 names, and with more a `Show all N done` / `Show fewer` `ui/Button` (`expanded` sets `aria-expanded`), remembered in sessionStorage. The server already sends every done task.
- `TaskRow.tsx`: `[review]  Name  60%` (the state by word, never the status number), a bold `YOU:` line on `needs_you` tasks, then `next:`. The row's bottom rule is its progress bar (`--pct`, set from the percent); a `needs_you` row reads `! [needs you]` and has a 2px `--warn` bar on its left.
- `taskWords.ts`: the pure wording: `statusTag`, `headerCounts`, `usageWords` (`Claude usage: 5-hour window 42% (resets 14:10) · week 18% · 5 agents · updated 2m ago`; a window that is null or past its reset reads `5-hour window --`), `queuedHeading`.
- `taskOrder.ts`: `needsYouFirst`, a stable split that puts `needs_you` tasks first. The sort is in this view only: the server's order also feeds the projector's task grid, which keeps it.

Status is always a word; colour is only a second cue, so it also works for colourblind users. Depends on `api` (types), `state`, `time` and `empty`.
