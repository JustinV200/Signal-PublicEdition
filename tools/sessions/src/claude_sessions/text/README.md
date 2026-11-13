# text

Shared text helpers, used by listings, the approval dialog, voice notes and status.

- `truncate(text, max_chars)`: one line, cut with an ellipsis.
- `first_sentences(text, count, max_chars)`: the start of a reply, for voice notes.
- `format_local_time(seconds)`, `format_local_time_ms(ms)`: e.g. `2026-10-19 15:42:07`.

Depends on: the standard library only.
