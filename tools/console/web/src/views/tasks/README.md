# views/tasks

The Tasks page (`Ctrl+5`): the task list the orchestrator reports with `console tasks set`, read from the `tasks` SSE event (`state.tasks`). Read only; nothing here sends a request.

- `TasksView.tsx`: header `TASKS  4 active · 1 needs you · overall 58%` with the usage line on the right, the active rows (the server's order: most finished first), then `Queued: N tasks, none started` and `Done today: N` with their names. Empty: `No tasks reported…`.
- `DoneGroup.tsx`: `Done today: N`; shows 6 names, and with more a `Show all N done` / `Show fewer` `ui/Button` (`expanded` sets `aria-expanded`), remembered in sessionStorage. The server already sends every done task.
- `TaskRow.tsx`: `[1 review]  Name  60%`, a bold `YOU:` line on `needs_you` tasks, then `next:`.
- `taskWords.ts`: the pure wording: `statusTag`, `headerCounts`, `usageWords` (`5h 42% (resets 14:10) · wk 18% · agents 5 · as of 2m ago`; a window that is null or past its reset reads `5h --`), `queuedHeading`.

Status is always the board's number plus a word; colour is only a second cue (the owner is colourblind). Depends on `api` (types), `state` and `time`.
