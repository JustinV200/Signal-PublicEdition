# audiohub.loop.conversation

The voice hub: wiring, the state machine and the three loops that run side by side.

## Public API

- `Conversation(settings, listen=True, parts=None)`
  - `await run()` starts the kernel, the Sonnet session, Whisper, Kokoro and Claude in parallel, then the IPC server, then opens the mic once.
  - It then runs the hearing, brain-turn and delivery loops until cancelled, until a client asks the IPC server to shut down (the console's Voice Stop), or until one fails. A shutdown request unwinds exactly like a cancel. The failure is raised as itself, not as an ExceptionGroup.
  - Raises `HubStartError` if the notification port is taken.
  - Once the port is bound, it writes `.cache/hub.json` (`{pid, create_time}`, owner-only, atomic) so the console's Stop can find a hub it didn't start, and removes it on the way out only while it still names this process. `parts.record_path` sets where (None writes nothing, as in tests).
- `ConversationParts` and `build_parts(settings, listen=True, io=None)`: the components, built for real or swapped in tests. `HubIo` replaces the local mic, the speaker or the status line. `music_pause` is None with `music.pause_on_wake` off; otherwise the brain reports its tool calls to it.
- `ConversationState`, the route types and `Phase` come from `routing/` (see `routing/README.md`): the pure state machine that says what each transcript means.
- `Delivery` also has `skip_unspoken_replies(before)`, which a request barge-in uses to drop Claude's stale direct replies. When a stop or barge-in cuts a batch, other agents' messages it never reached go back to the kernel (`Kernel.requeue`) and are spoken next; Claude's are dropped. Each spoken message gets its own `speaking:` status line with its full text, so the console's voice feed shows everything said.
- `VoiceBrain`: the protocol `ClaudeBrain` satisfies.
- `CLAUDE_SOURCE`, `BACKGROUND_SOURCE`, `HUB_SOURCE`: kernel message sources.

## Messages sent to the kernel

| What | source | priority | notes |
|---|---|---|---|
| each `ReplyText` of a turn | `claude` | high | `is_direct_reply=True` |
| text from outside a turn (`on_background_text`) | `claude-background` | normal | |
| "couldn't reach Claude" after a failed or stalled turn | `audiohub` | high | |
| "I lost some of what you said" when queued speech is dropped to fit the cap | `audiohub` | high | |

## Files

| File | Contents |
|---|---|
| `conversation.py` | `Conversation`: startup, shutdown, routing heard transcripts, the wake chime, holding the music and the echo log |
| `routing/` | `ConversationState`, its echo checks and speech timing, the route types |
| `turns.py` | `BrainTurns`: request queue, brain to kernel, background text. Requests heard during a turn are merged into one, capped at 1500 characters; dropping the oldest to fit is announced out loud. A failed or stalled turn is announced too. |
| `delivery.py` | `Delivery`: kernel batches to speech, echo tail, mic pause (half-duplex) or sentence and audio-end timing (barge-in), skip after stop |
| `outbox.py` | message sources and submit helpers |
| `parts.py` | `ConversationParts`, `HubIo`, `build_parts` |
| `hub_record.py` | `write_hub_record` / `remove_hub_record`: the hub's own pid record for the console |
| `activity.py` | `ConversationActivity`: the state and kernel as `MusicPause` asks about them |
