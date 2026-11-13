# audiohub.loop.conversation.routing

What each heard transcript means: the hub's state machine. Pure logic with no I/O, so it is easy to test. Times are `time.monotonic()` seconds passed in by the caller.

## Public API

- `ConversationState(wake_settings, *, is_barge_in=False, echo_lag_s=0.0, reply_after_s=0.0)`
  - `route(transcript, heard_at, *, heard_until=None)` returns `Ask`, `Attend`, `Cancel`, `Echo` (the mic re-heard Claude), `Ignore`, or `BargeIn(then)`: the user cut in over Claude, so cut its speech, then follow `then` (`Ask`, `Attend` or `Cancel`). The talk-over and echo-tail rules are in `loop/README.md`. Fields that only explain a route take no part in equality: `Ask.has_wake_phrase` (the hub chimes) and `Echo.compared_with` / `Echo.started_after_audio_s` (for the log).
  - `phase` (`Phase.LISTENING` / `THINKING` / `SPEAKING`).
  - Transitions: `turn_started/finished` (a start closes the follow-up window), `speech_started`, `sentence_started(now, text)`, `speech_interrupted(now, heard_until)` (a barge-in: audio cut at `now`, talk-over over once the barge-in utterance ended; closes the follow-up window), `speech_audio_ended(now, *, is_cut=False)` (the batch stopped playing: its echo tail starts, replies count from `reply_after_s` later, and the follow-up window opens unless a barge-in or a stop cut it, or `follow_up_s` is 0), `speech_finished(now, spoken_text)` (the tail is over too), `open_follow_up(now)`, `close_follow_up()`, `is_in_follow_up(at)`.
  - The window `speech_audio_ended` opens starts at that audio end, so what was said while it was shut (chatter while Claude thought, transcribed late) isn't a follow-up. If a window is still open then, it goes on instead, keeping its start. One that already expired is kept beside the new one, so a reply begun in its last moments but routed after that audio end still counts. `close_follow_up` shuts both. `open_follow_up` (after a bare "Hey Claude") has no start.
  - `tail_offset(heard_at)`: how long after a played-out batch's audio ended an utterance begun in its echo tail began (else None), for the log.
- The route types `Ask`, `Attend`, `BargeIn`, `Cancel`, `Echo`, `Ignore`, `Route`, and `Phase`.

## Files

| File | Contents |
|---|---|
| `state.py` | `ConversationState`: phase, follow-up window, routing |
| `echo_check.py` | `EchoCheck` (internal): which echo check applies, by when an utterance began |
| `speech_window.py` | `SpeechWindow`, `SpeechHistory` (internal): when one batch was audible, when its audio ended or a barge-in cut it, when replies to it start, and which sentence played when, for the last 3 batches |
| `routes.py` | the route types and `Phase` |

## Dependencies

`audiohub.config` (`WakeSettings`) and `audiohub.loop.phrases`.
