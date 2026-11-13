# audiohub.loop.phrases

Pure text parsing of the user's transcripts. No I/O, no state.

## Public API

- `match_wake(transcript, phrases) -> str | None`
  - Returns the request with the wake phrase stripped, in the user's own words, or `""` when they said only the wake phrase. Returns `None` when they weren't addressing Claude.
  - The wake phrase must come first ("Hey Claude, ..."), optionally after a filler ("Okay, Claude ..."), or last after a comma ("What's the time, Claude?"). "Hey Signal" works too, and a phrase "hey X" also counts as just "X" in that last position ("Thanks, Signal"), never at the start.
  - Case- and punctuation-insensitive. Accepts mis-hearings: "claud", "clawed", "clod" anywhere, and "cloud" only after "hey" ("hey cloud").
- `is_stop_command(request) -> bool`: "stop", "cancel", "never mind", "be quiet" and similar, with nothing else, so "stop the music" is not one.
- `is_echo_of_ending(transcript, spoken) -> bool`: True when the transcript reads as the last words of `spoken`, in order, the way an echo heard in the echo tail would, once the user heard Claude stop. With fewer than two content words (words outside the small `COMMON_WORDS` set) it must be exactly Claude's last words; otherwise its content words must line up with Claude's last ones with at most a quarter misheard, missed or extra, though a leading yes/no word Claude didn't say there is never one of those ("Yes, delete the old logs." after "...delete the old logs?" is a reply). So "do it?" after "...should I do it?" is an echo, but "do it", "yes" or "go ahead" said where Claude used those words earlier, or in another order, are not.
- `is_echo(transcript, last_spoken) -> bool`: the check after the echo tail: alone with barge-in off; with barge-in, alone for a stop or wake phrase, and for anything else only together with `is_exact_ending`. True when a transcript of 3 or more words is mostly (75%+) words from the end of what Claude just said, in any order. A lone "yes" is never an echo.
- `is_exact_ending(transcript, spoken) -> bool`: True when the transcript's words, ignoring only case and punctuation, are exactly the last words of `spoken`. With barge-in, a reply after the echo tail is dropped only if this and `is_echo` both hold, so "Please delete the old logs." after "...delete the old logs?" is a reply there.
- `is_echo_during_speech(transcript, recently_spoken) -> bool`: the stricter check for barge-in, for a transcript heard while Claude was audible. True when every word of it appears in the sentences Claude said around then, or, for 3 or more words, 75%+ do. So Claude's own "stop" or "Claude" doesn't read as a command. Words are compared after mapping wake-word soundalikes to the wake word (`wake.canonical_words`, used inside the package), and a heard word of 4+ letters also matches a spoken word it starts.
- `has_words(text) -> bool`

## Files

- `tokens.py`: word tokens with their original spans
- `wake.py`, `stop.py`, `echo.py`: the matchers; `yes_no.py`: the yes and no words `echo.py` uses

## Dependencies

Standard library only.
