# views/chat

The session log. `ChatView` lays out `DateDivider`, `MessageRow` (you / claude / action / note; an action row ends with where its run has got to: sending, working, done with what happened (`sent` only on replayed rows from before buttons ran in the server), and a failed one adds the error and a Retry button), `WorkingRow` (the `working m:ss` clock while the orchestrator is busy) and `EmptyChat`, and follows the bottom through the `scroll` package.

Public API: `index.ts`. Depends on `state`, `markdown`, `time`, `scroll`.
