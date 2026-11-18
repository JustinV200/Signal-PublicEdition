# views/voice

The voice buffer: `VoiceView` shows `Running · <phase>` or `Stopped`, who started it (`started by the console` or `started outside the console`, `status`'s `startedByWords`), and one button that runs right away and whose label follows Voice's state (`voiceButton.ts`): `Start voice` while stopped, `Stop voice` while running or `starting` (the server lets a stop through while a start is still loading, so a slow or hung start can be stopped), reading "Working…" only while the action named on it is pending. Its outcome shows on the shell's result strip (`app`). Then the feed of `FeedRow`s (`heard` quoted, `said` plain, `note` faint), newest at the bottom; an empty feed shows the shared `empty` state (`NOTHING HEARD YET`, `When Voice hears or says something, it shows here.`).

Public API: `index.ts` (`VoiceView`, and `voiceButton` for its tests). Depends on `state`, `status`, `time`, `scroll`, `empty`, `ui`.
