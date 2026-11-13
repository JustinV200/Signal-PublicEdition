# audiohub.loop

The voice conversation loop. It hears the user through the glasses, sends what they ask to Claude, and speaks the replies, which the kernel orders, with music ducked.

```
mic -> Hearing (VAD + Whisper) -> route (wake / follow-up / stop)
    -> BrainTurns (ClaudeBrain) -> Kernel -> Delivery -> VoiceOutput (duck, TTS, play)
```

## Public API (`from audiohub.loop import ...`)

### Phrases (pure)
- `match_wake(transcript, phrases) -> str | None`
- `is_stop_command(request) -> bool`

See `phrases/README.md`.

### Speaking
- `VoiceOutput(synthesizer, speaker, ducker)`
  - `await speak(text, voice=None) -> bool` and `await speak_many(texts, voice=None) -> bool` run clean, then split, then synthesize in an executor while the previous chunk plays.
  - The music is ducked once per call and always restored, on errors and cancellation too. Duck and restore run in order on one dedicated thread. A call already waiting for the output when the one before it ends (speech queued behind the chime) keeps its duck instead of restoring and ducking again.
  - A chunk the device fails to play (`AudioStreamError`, e.g. the Speaker's stall deadline) is logged and skipped, and the call returns `False`.
  - `speak_many(texts, voice=None, on_chunk=None)` calls `on_chunk(text)` as each sentence chunk starts playing. Barge-in uses it to know what Claude said when.
  - `await play_cue(samples, sample_rate) -> bool` plays a short non-speech sound (the wake chime) with the music ducked. It isn't speech: `speaking` stays False and `stop()` leaves it alone. Speech and cues take turns on the output.
  - Also `speaking`, `stop()` (cuts the current chunk and skips the rest), `await warm_up()` (loads Kokoro) and `close()` (shuts the ducking thread after any queued restore).
- `create_voice_output(settings, speaker=None)`: the real Kokoro, `Speaker` and `Ducker` wiring. `speaker` replaces the output device, e.g. with the phone's `RemoteSpeaker`.

### Hearing
- `Hearing`, `Heard`, `FrameSource` and `WavFrameSource` (see `hearing/README.md`).
- `create_hearing(settings, source=None)`: VAD and Whisper over the configured mic or a stand-in.

### Music pause
- `MusicPause(music, resume_after_s, *, sleep=asyncio.sleep)`: pauses the music while the user talks with Claude (`music.pause_on_wake`).
  - `hold()`: the user said the wake phrase or a request. Returns at once.
  - `note_tool_call(tool_name)`: the brain's `on_tool_call`, for `mcp__audiohub__` tools only. A `music_play`, `music_pause`, `music_search_and_play` or `music_play_liked` call during a session leaves the music to the user; `music_next` or `music_previous` makes whatever is paused resume.
  - `await run(hub)`, with `hub` a `HubActivity` (`is_busy()`, `is_conversation_open()`), until cancelled.

### The hub
- `Conversation(settings, listen=True, parts=None)`: `await run()` until cancelled.
  - `parts=None` builds the real parts with `build_parts(settings, listen, io=None)`.
  - `HubIo(source=None, speaker=None, status=None)` swaps the local mic (e.g. for a `WavFrameSource`), the output device and the console status line. `run --phone` passes the phone's source and speaker, plus a `StatusLine` that mirrors to the page.
  - `ConversationParts` holds kernel, server, voice, status, hearing, brain and music_pause, so tests can swap any of them.
  - Raises `HubStartError` when the notification port is taken.
- `ConversationState`, `Phase`: see `conversation/README.md`.

### Console
- `StatusLine(stream=None, clock=datetime.now, on_show=None)`. `show(label, detail="")` prints `[HH:MM:SS.t] label: detail`, skipping exact repeats, and passes each printed `(label, detail)` to `on_show`.
- `quote(text, max_chars=90, *, keep_end=False)` and `format_duration(seconds)`.

## Behaviour notes

- **Wake.** A transcript reaches Claude if:
  - it starts with a wake phrase,
  - it ends with ", Claude",
  - it arrives once the user has heard Claude's audio end (`audio.reply_after_s` after it), until `wake.follow_up_s` after its echo tail (never, when that is 0), or after a bare "Hey Claude". The window closes as soon as a request is accepted (or after "stop", which also keeps the batch it cut from reopening it), so chatter while Claude thinks needs the wake phrase again, even if Whisper only routes it after Claude's next audio ends (the window that opens then starts there, unless the last one is still open, and a reply begun in the last one still counts),
  - or `wake.require_wake` is false.
- **Barge-in** (`audio.barge_in`, on by default). The mic, segmenter and Whisper keep running while Claude speaks. Each batch counts as audible from its first sentence until `audio.echo_tail_s` (2 s) after its audio ends, since Bluetooth output lags about 1.7 s.
  - An utterance begun in that echo tail, once the user heard the batch end (`audio.reply_after_s`, 1.3 s, after its audio ended, at most `echo_tail_s`), is a reply. It is an echo, and dropped, only if it reads as Claude's last words in order: exactly, when it has fewer than two content words ("do it?" after "...should I do it?"), else with at most a quarter of its content words off, though a leading "yes" or "no" Claude didn't say there is never forgiven ("Yes, delete the old logs." is a reply). Matching words earlier or in another order are the user answering ("go ahead", "yes"). A stop or wake phrase is also dropped if it mostly repeats Claude's recent sentences (the talk-over check below). Otherwise it is routed as usual, with the follow-up window open, and doesn't cut anything.
  - An utterance begun while Claude was still playing, or in the tail before the user could hear it end, is routed by the talk-over rules. Before then, what the mic hears is almost always Claude's own voice, and one misheard word would turn it into a reply. It is an echo, and dropped, if every word of it, or for 3+ words 75% of them, appears in the sentences Claude said around then. A sentence counts until `echo_tail_s` plus a 1 s timing margin after the next one started, so "stop" or "Claude" in Claude's own sentence doesn't interrupt it. Mishearings still match: wake-word soundalikes ("Clawed") count as "Claude", and a heard word of 4+ letters matches a spoken word it starts ("stop" in "stopped"). The cost: a real "stop" is ignored while Claude's recent sentence contains "stop" or a word starting with it.
  - The last 3 batches are kept, because the next batch may start while Whisper is still on the previous batch's last utterance.
  - "Stop" (or any stop command), with or without a wake phrase, cuts the speech and then does what "Claude, stop" does.
  - "Hey Claude, <request>" cuts the speech and is asked as usual. The rest of the batch is dropped (other agents' messages in it are logged), Claude's other unspoken direct replies from before the cut are skipped. A bare "Hey Claude" does the same and opens the follow-up window.
  - Anything else is ignored: no follow-up window and no `wake.require_wake = false` while Claude talks.
  - Each dropped echo is logged at INFO with the transcript, the end of Claude's text it matched, and when it began relative to the end of Claude's audio; the status line says the same. Every other utterance begun in the echo tail is logged with its offset and what it was routed as, so `audio.reply_after_s` can be tuned from both sides.
  - After a cut, what the user says after the barge-in utterance ended is routed normally again, but the cut sentence's echo is still checked until the tail ends, and the follow-up window doesn't reopen.
- **Half-duplex** (`audio.barge_in = false`). The mic is paused while Claude speaks and for `audio.echo_tail_s` after. On resume, audio buffered during the pause is discarded and the segmenter reset. "Claude, stop" works while Claude is thinking or between messages. Three things differ from the old half-duplex loop on purpose: a batch that "stop" cut short opens no follow-up window, "stop" closes the window, so chatter after it needs the wake phrase again, and chatter said while the window was shut no longer gets in when Whisper routes it after the tail (see Wake).
- **Echo after speech.** In both modes, a transcript of 3+ words heard within 4 s of the tail ending is dropped if 75% or more of its words, in any order, are among Claude's last few (as many as it has, plus 4). With barge-in, Claude's voice no longer reaches the live mic by then, so a reply must also be word for word Claude's last words to be dropped ("yeah, do that one" after "...should I do that one?" and "Please delete the old logs." after "...delete the old logs?" get through); a stop or wake phrase gets the in-any-order check alone.
- **Wake chime** (`audio.wake_chime`, on by default). A bare "Hey Claude" or a request with a wake phrase plays a soft 0.27 s two-tone chime through the voice output (glasses or phone, music ducked), at `audio.wake_chime_volume`. It opens no speech window, so what the user says next isn't talk-over and isn't echo-checked against it.
- **Mic stays open.** The microphone opens once for the whole run (half-duplex mutes it with `paused`). Opening the glasses' mic switches them to Hands-Free, which takes 1-2 s.
- **Requests while Claude works** are merged into one request that runs after the current turn, capped at 1500 characters. If older speech has to be dropped to fit, Claude says so. A turn that shows no activity for `brain.turn_stall_timeout_s` (300 s) is given up on, the user hears that it failed, and the next request runs as usual.
- **"Claude, stop"** interrupts the turn, drops queued requests, cuts current speech, and never speaks Claude's unspoken messages from before the stop.
- **Music pause** (`music.pause_on_wake`, on by default; despite the name it covers notifications too). An accepted request or wake phrase pauses the music if it is playing, and so does the hub starting to speak (a notification). It stays paused while Claude thinks or speaks and, once the user has spoken, while the follow-up window is open or messages wait in the kernel. The kernel's Sonnet dispatcher never holds a message, so the wait is at most one decision. `music.resume_after_s` (2 s) after all that, it is resumed, but only if it is still paused on the same track (title and artist) and Claude wasn't asked to play or pause it. After Claude skipped a track (`music_next`, `music_previous`), whatever is paused is resumed, so the new track plays. Music that wasn't playing is never started, and it is paused at most once per conversation, so music the user starts meanwhile keeps playing. Every music call runs in the music pause's own task with a 5 s cap, so a slow or missing backend never delays the reply; the cap can't cut the Windows media session's synchronous WinRT calls, only awaits. Failures are logged, and a pause that failed or timed out is never resumed. Stopping the hub (Ctrl+C) mid-conversation leaves the music paused.
- **Talking over the user.** Before asking the kernel for a batch, the output waits up to 10 s for the user to finish an utterance.

## Files

| Path | Contents |
|---|---|
| `voice_output.py` | `VoiceOutput` |
| `status.py` | `StatusLine` and formatting helpers |
| `factories.py` | `create_voice_output`, `create_hearing` |
| `chime.py` | the wake chime: `make_chime`, `WakeChime` |
| `music_pause.py` | `MusicPause`, `HubActivity`: music paused for conversations |
| `tasks.py` | `run_tasks`: run coroutines as one unit |
| `phrases/` | wake, stop and echo parsing |
| `hearing/` | frame sources and `Hearing` |
| `conversation/` | state machine, brain turns, delivery, `Conversation` |

## Dependencies

`audiohub.config`, `audiohub.audio`, `audiohub.stt`, `audiohub.tts`, `audiohub.brain`, `audiohub.kernel` and `audiohub.music`, all through their entry points.
