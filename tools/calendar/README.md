# calendar

Read-only Google Calendar access for the owner's idle board. It reads the calendars ticked in Google Calendar's sidebar on `owner@example.com` and keeps the next 14 days in `.state/agenda.json`, refreshed every 10 minutes by a scheduled task. Deterministic, no LLM.

It calls the Calendar v3 REST API directly with `google-auth`'s `AuthorizedSession`, on the mail tool's OAuth client (same Google Cloud project).

## Setup

Follow **[SETUP.md](SETUP.md)**: enable the Calendar API on the mail tool's project, add the two read-only scopes to the consent screen, run `calendar add` once, and register the scheduled task.

The root `.gitignore` has `tools/calendar/.state/`.

## CLI

```
calendar setup                      # the steps, plus a check of the client file and sign-in
calendar add [--email ADDRESS]      # one-time browser sign-in (default owner@example.com)
calendar agenda [--days N] [--json] # upcoming events (default 14 days, 1-60)
calendar sync-cache                 # rewrite .state/agenda.json (what the scheduled task runs)
```

Run them as `uv run --project tools/calendar --frozen calendar ...` from the repo root. Errors print one `calendar: error: ...` line to stderr and exit 2.

## The cache

`.state/agenda.json`, replaced atomically on each successful `sync-cache`:

```json
{"updated": "2026-10-20T14:10:00-04:00",
 "events": [{"start": "2026-10-21T09:00:00-04:00", "end": "2026-10-21T10:00:00-04:00",
             "all_day": false, "title": "CHEM 120", "calendar": "the owner"}],
 "skipped": []}
```

- Covers now to 14 days ahead, across every selected calendar, sorted by start (all-day first on the same day). Events already under way are included.
- Timed `start`/`end` are local time with an offset. All-day ones are `YYYY-MM-DD`, and `end` is Google's exclusive end date. `end` is `null` if Google gives none.
- Only the title (one line, at most 80 chars) and calendar name are kept. The API is asked for just `status`, `summary`, `start` and `end`, so attendees, descriptions, locations and links never reach the tool.
- One calendar the API refuses (say a shared calendar that's still ticked but no longer readable) is left out and named in `skipped`; the rest are still written.
- A failed sync (offline, signed out, calendar list or every calendar failing) writes nothing: the old cache stays, so `updated` shows how stale it is.
- Each sync's outcome also goes to `.state/sync_status.json` (`{"ok", "at", "kind", "message"}`, plus `"skipped"` when some calendars were unreadable), since the scheduled run has no stderr. `calendar setup` prints it.

## Security

- **Scopes**: exactly `calendar.events.readonly` and `calendar.calendarlist.readonly`. The tool can't create, edit or delete anything.
- **Token at rest**: `.state/token.bin` holds `{"email", "refresh_token"}`, encrypted with Windows DPAPI (CurrentUser, calendar-only entropy) and written atomically to an owner-only file (`packages/googleauth`). Access tokens stay in memory.
- **No secrets out**: the refresh token and the client secret never appear in output or errors. Library auth errors are replaced with fixed messages (`from None`), and a revoked sign-in says "Re-run `calendar add`".
- **Sign-in listener**: the shared one-shot loopback server on `127.0.0.1` (random port, OAuth `state` and PKCE), only while `calendar add` runs.

## Later phase (not built)

brief-me §9's Claude-run calendar: the `calendar.app.created` scope, a "Signal" calendar written from `life/`, and the sync rules there. It needs a new consent and a new `calendar add`.

## Layout

`src/calendar_tool/` holds `auth/`, `google_api/`, `agenda/` and `cli/`, each with a README, plus `paths.py` and `errors.py`. cli uses agenda and auth; both use google_api; everything uses errors. `schedule/` has the scheduled task scripts.

Dependencies:

- `google-auth`: credentials, refresh, `AuthorizedSession`.
- `requests`: the transport (same pin as mail).
- `signal-googleauth`: `packages/googleauth`, the shared client file check, browser flow and DPAPI.
- `signal-jsonstate`: `packages/jsonstate`, the atomic JSON write for the cache.

## Development

```
uv run --frozen pytest
uv run --frozen ruff check src tests
uv run --frozen ruff format src tests
```

The tests use a fake Calendar HTTP session and a fake browser flow, and make no network calls. The sign-in test uses real DPAPI and runs on Windows only. The live sign-in is tested by hand.
