# calendar_tool.agenda

Turns the Calendar API's events into the idle board's agenda and writes the cache. Deterministic, no LLM.

## Public API

- `fetch_agenda(client, now, days=14, zone=None) -> (list[AgendaEvent], skipped names)`: every event overlapping `[now, now + days)` on the selected calendars, sorted by start (all-day first on the same day). Cancelled events and events with an unreadable start are dropped. A calendar whose events the API refuses (`ApiError`) is skipped and named; network and sign-in failures, a failed calendar list, or every calendar failing still raise.
- `AgendaEvent`: `to_json()` gives `{"start", "end", "all_day", "title", "calendar"}`.
  - Timed: `start`/`end` are ISO 8601 with the local offset (`zone=None` uses this PC's zone, DST-aware).
  - All-day: `start`/`end` are `YYYY-MM-DD`; `end` is Google's exclusive end date (the day after a one-day event).
  - `end` is `null` when Google gives none.
  - `title` is one line, control and bidi characters removed, at most 80 chars (cut with `…`); `(no title)` when empty. `calendar` is at most 40.
- `agenda_payload(events, updated, skipped)`: `{"updated": ISO 8601, "events": [...], "skipped": [calendar names]}`.
- `sync_cache(client, cache_path, now, zone=None) -> (count, skipped)`: fetches 14 days, then replaces the file through `signal_jsonstate.write_json_atomic`. A failed fetch raises before anything is written, so the old cache stays.

## Files

- `normalize.py`: `AgendaEvent`, `normalize_event`, `clean_text`.
- `fetch.py`: `fetch_agenda`.
- `cache.py`: `agenda_payload`, `sync_cache`.

## Depends on

`calendar_tool.google_api`, `calendar_tool.errors`, `signal_jsonstate`.
