# views/voice

The voice buffer: `VoiceView` shows `Running · <phase>` or `Stopped`, who started the hub, and Start / Stop buttons that run at once (the one that does not apply is disabled with its reason; a clicked one reads "Working…" until the console has run it; while the hub is `starting`, Stop works and Start waits), the last Start/Stop outcome in words (`lastAction.ts`), a hint, then the feed of `FeedRow`s (`heard` quoted, `said` plain, `note` faint), newest at the bottom.

Public API: `index.ts`. Depends on `state`, `status`, `time`, `scroll`, `ui`.
