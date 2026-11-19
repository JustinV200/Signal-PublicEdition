# calendar_tool.agenda

Turns the Calendar API's events into the idle board's agenda and writes the cache. Deterministic, no LLM.

## Public API

- `fetch_agenda(client, now, days=14, zone=None) -> (list[AgendaEvent], skipped names)`: every event overlapping `[now, now + days)` on the selected calendars, sorted by start (all-day first on the same day). Cancelled events and events with an unreadable start are dropped. A calendar whose events the API refuses (`ApiError`) is skipped and named; network and sign-in failures, a failed calendar list, or every calendar failing still raise. `DEFAULT_DAYS` is 14, `MAX_DAYS` 60.
- `normalize_event(raw, calendar, zone)`: one raw event (from a list, a read or a write) to an `AgendaEvent`, or None when it's cancelled or unreadable.
- `AgendaEvent`: `to_json()` gives the cache's `{"start", "end", "all_day", "title", "calendar"}`; `to_detail_json()` adds `{"id", "calendar_id", "mine", "recurring", "invite"}` for the CLI and MCP results.
  - Timed: `start`/`end` are ISO 8601 with the local offset (`zone=None` uses this PC's zone, DST-aware).
  - All-day: `start`/`end` are `YYYY-MM-DD`; `end` is Google's exclusive end date (the day after a one-day event).
  - `end` is `null` when Google gives none.
  - `title` is one line, control and bidi characters removed, at most 80 chars (cut with `…`); `(no title)` (`NO_TITLE`, also used by the change dialog) when empty. `calendar` is at most 40.
  - `mine`: the tool's private marker is set. `recurring`: an occurrence of a series. `invite`: the owner's response when someone else invited him, else `null`.
- `agenda_payload(events, updated, skipped, is_detailed=False)`: `{"updated": ISO 8601, "events": [...], "skipped": [calendar names]}`, with detailed rows when asked.
- `sync_cache(client, cache_path, now, zone=None) -> (count, skipped)`: fetches 14 days, then replaces the file through `signal_jsonstate.write_json_atomic`. A failed fetch raises before anything is written, so the old cache stays. The cache always has the five-field rows.
- `refresh_cache(client, cache_path, status_path, now) -> bool`: `sync_cache` after a write, recording the outcome in the status file. It never raises: False (logged) means the board stays stale until the scheduled sync.
- `record_sync_status(path, at, error=None, skipped=None)`, `describe_sync_status(path)`: the last sync's outcome in `.state/sync_status.json` (`{"ok", "at", "kind", "message"}`, plus `"skipped"`), since the scheduled run has no stderr.

## Files

- `normalize.py`: `AgendaEvent`, `normalize_event`, `clean_text`.
- `fetch.py`: `fetch_agenda`.
- `cache.py`: `agenda_payload`, `sync_cache`.
- `refresh.py`: `refresh_cache`.
- `sync_status.py`: the status file.

## Depends on

`calendar_tool.google_api`, `calendar_tool.errors`, `signal_jsonstate`.
