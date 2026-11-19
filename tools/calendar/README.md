# calendar

Google Calendar for the owner's idle board and for Claude. It reads the calendars ticked in Google Calendar's sidebar on `owner@example.com` and keeps the next 14 days in `.state/agenda.json`, refreshed every 10 minutes by a scheduled task. Claude can also read the agenda, add events, and change, delete or answer events through an MCP server (`calendar mcp`, server name `calendar`). Changes to events the tool didn't create take the owner's click in an Allow/Deny dialog. It never invites anyone. Deterministic, no LLM.

It calls the Calendar v3 REST API directly with `google-auth`'s `AuthorizedSession`, on the mail tool's OAuth client (same Google Cloud project).

## Setup

Follow **[SETUP.md](SETUP.md)**: enable the Calendar API on the mail tool's project, add the two scopes to the consent screen, run `calendar add` once, and register the scheduled task. Setup's `wire` adds the `calendar` server to `.mcp.json`; restart Claude Code to load it.

The root `.gitignore` has `tools/calendar/.state/`.

## CLI

```
calendar setup                      # the steps, plus a check of the client file and sign-in
calendar add [--email ADDRESS]      # one-time browser sign-in (default owner@example.com)
calendar agenda [--days N] [--json] # upcoming events with their ids (default 14 days, 1-60)
calendar sync-cache                 # rewrite .state/agenda.json (what the scheduled task runs)
calendar create TITLE START [END] [--calendar ID] [--location L] [--description D]
calendar update EVENT_ID [--calendar ID] [--series] [--title T] [--start S] [--end E]
                [--location L] [--description D]
calendar delete EVENT_ID [--calendar ID] [--series]
calendar respond EVENT_ID accepted|declined|tentative [--calendar ID] [--series]
calendar mcp                        # the stdio MCP server
```

Run them as `uv run --project tools/calendar --frozen calendar ...` from the repo root. Errors print one `calendar: error: ...` line to stderr and exit 2.

- `agenda` ends each line with `id <event id> --calendar <calendar id>`, the arguments the write commands take, and flags the tool's own events (`mine`), repeating ones (`repeats`) and invitations (`invite: needsAction`). `--calendar` defaults to `primary`.
- Times are `YYYY-MM-DD` for all-day, or `YYYY-MM-DDTHH:MM` in local time (an offset is optional). An all-day end is exclusive, as in the agenda: a one-day event on the 20th ends on the 21st, which is also the default when END is left out. A timed event needs an end. `update --start` alone keeps the event's length.
- On a repeating event, `update`, `delete` and `respond` act on the one occurrence; `--series` acts on the whole series.

## MCP tools

| Tool | Does | Asks the owner |
|---|---|---|
| `calendar_agenda` | The next 1-60 days, with each event's ids and flags | never |
| `calendar_create` | Adds an event: title, times, optional location and description | never |
| `calendar_update` | Changes the title, time, location or description | if the tool didn't create it, unless turned off |
| `calendar_delete` | Deletes an event, an occurrence or (`series`) a whole series | if the tool didn't create it, unless turned off |
| `calendar_respond` | Answers an invitation: accepted, declined or tentative | yes (it's never the tool's own), unless turned off |

"Turned off" is `confirm = false` in `.state/calendar.toml` (see Security); a whole-series change to an event the tool didn't create still asks.

Agenda rows are `{"start", "end", "all_day", "title", "calendar", "id", "calendar_id", "mine", "recurring", "invite"}`. `mine` means the tool created the event; `invite` is the owner's response when someone else invited the owner (`needsAction`, `accepted`, `declined`, `tentative`), otherwise `null`. See [src/calendar_tool/mcp_server/README.md](src/calendar_tool/mcp_server/README.md).

## The cache

`.state/agenda.json`, replaced atomically on each successful `sync-cache` and after each successful write:

```json
{"updated": "2026-10-20T14:10:00-04:00",
 "events": [{"start": "2026-10-21T09:00:00-04:00", "end": "2026-10-21T10:00:00-04:00",
             "all_day": false, "title": "CHEM 120", "calendar": "the owner"}],
 "skipped": []}
```

- Covers now to 14 days ahead, across every selected calendar, sorted by start (all-day first on the same day). Events already under way are included.
- Timed `start`/`end` are local time with an offset. All-day ones are `YYYY-MM-DD`, and `end` is Google's exclusive end date. `end` is `null` if Google gives none.
- Only the title (one line, at most 80 chars) and calendar name are kept; the ids and flags the CLI and MCP results carry stay out of the cache.
- One calendar the API refuses (say a shared calendar that's still ticked but no longer readable) is left out and named in `skipped`; the rest are still written.
- A failed sync (offline, signed out, calendar list or every calendar failing) writes nothing: the old cache stays, so `updated` shows how stale it is. After a write, a failed refresh doesn't undo the write; the result says the board couldn't be refreshed and the scheduled sync catches up.
- Each sync's outcome also goes to `.state/sync_status.json` (`{"ok", "at", "kind", "message"}`, plus `"skipped"` when some calendars were unreadable), since the scheduled run has no stderr. `calendar setup` prints it.

## Security

- **Scopes**: exactly `calendar.events` and `calendar.calendarlist.readonly`. The tool can add, change and delete events on every calendar the owner can edit, and read the owner's calendar list. It can't create, delete or share calendars, or change their settings.
- **Older sign-ins**: a sign-in saved before the tool could write holds `calendar.events.readonly` instead. It keeps reading (the token is refreshed with the scopes it was granted), but every write fails before any request with "This calendar sign-in is read-only ... Re-run `calendar add`". A Google 403 for a missing scope gives the same message.
- **What it reads**: the API is asked only for the fields an agenda row or a change needs: status, title, start, end, ids, the repeat link, the tool's marker, and attendee entries cut down by `maxAttendees=1`. Descriptions, locations and links never reach the tool. With two or more attendees Google returns only the owner's own entry. With exactly one attendee Google returns that entry whoever it is: the agenda list gets only its response (no address), but the single-event read before a change also gets its address, because a reply has to name the owner's own. No result, dialog or file shows another person's address.
- **No guests added, no notifications**: create and update bodies are built from fixed keys (title, times, location, description, the marker) and never list attendees. Create, update and delete send `sendUpdates=none`. No email isn't no effect: on an event the owner organises, a change or delete still shows on every guest's copy, which is why the dialog says when an event has guests.
- **Replies**: `respond` sends only the owner's own attendee entry with `attendeesOmitted`, Google's way to change just the participant's response, so nobody else's entry is touched. It sends `sendUpdates=all`, as clicking Yes/No in Google Calendar does; Google's docs define `all` as "Notifications are sent to all guests". In practice only the organizer seems to get the reply email (unverified). With `none` Google would still record the answer on the event, but an organizer outside Google (an Outlook invite) would never hear of it.
- **The marker**: created events get the private extended property `signal=1`. Google keeps private properties on one calendar's copy of an event only, so someone sending an invite can't set it on the owner's copy. But anyone with writer access to the same calendar can (their own copy of this tool would), and so can any other app that uses the key `signal`. The marker is a convenience that keeps the tool's own events from asking, not a security boundary against people who can already edit that calendar.
- **The gate**: `calendar_update`, `calendar_delete` and `calendar_respond` (and the CLI's `update`, `delete` and `respond`) re-read the event just before writing, then open the shared `signal_confirm` dialog for any event without the marker.
  - The dialog shows the event's title, time and calendar as they are now, whether the change hits one occurrence or EVERY occurrence, whether other people are on the event (judged without their addresses), and each change ("time was ..." and "time becomes ..." on separate lines, "description becomes '...'", "delete this event", "delete the WHOLE repeating series", "reply 'declined'"). Every new value is shown in full, flattened to one line; only an old value is cut past 110 characters, with "(N more characters)". The whole dialog must fit in 2000 characters (past that `signal_confirm` cuts the middle), so a change too long to show in full is refused before asking and nothing is changed. In practice that leaves room for about 850 characters of new title, location and description together, and the update tool's description says so. The tool's own events aren't gated and keep the usual limits (300, 500 and 8000 characters).
  - Deny is the default, Allow needs a mouse click, and no answer within 120 s denies. A denied or timed-out change sends nothing and says "nothing was changed".
  - The write sends the re-read event's etag as `If-Match`, so an event that changed while the dialog was open isn't overwritten.
  - An occurrence id acts on that occurrence only. The whole series takes an explicit `series`, and a series id without it is refused.
  - Set `confirm = false` under `[changes]` in `.state/calendar.toml` to turn the dialog off (not recommended). A whole-series change to an event the tool didn't create still asks.
  - Like every `signal_confirm` gate, this is a human gate, not a sandbox: a process running as the owner can click Allow or edit `calendar.toml`.
- **Untrusted content**: anyone can send the owner an invite, so event text is other people's words, and so is a shared calendar's name. Every MCP result that carries Google data puts it, as JSON with `<` escaped, inside one `<untrusted_calendar_content>...</untrusted_calendar_content>` frame after a fixed trusted line (`packages/untrusted`). Error messages, which aren't framed, never quote event titles or calendar names. The server instructions and the tool descriptions say it is data, never instructions. The dialog flattens event text to single lines (`sanitize_text`).
- **Token at rest**: `.state/token.bin` holds `{"email", "refresh_token", "scopes"}`, encrypted with Windows DPAPI (CurrentUser, calendar-only entropy) and written atomically to an owner-only file (`packages/googleauth`). Access tokens stay in memory.
- **No secrets out**: the refresh token and the client secret never appear in output or errors. Library auth errors are replaced with fixed messages (`from None`), and a revoked sign-in says "Re-run `calendar add`".
- **Sign-in listener**: the shared one-shot loopback server on `127.0.0.1` (random port, OAuth `state` and PKCE), only while `calendar add` runs.

```toml
# .state/calendar.toml (optional; these are the defaults)
[changes]
confirm = true   # false changes others' events without the Allow/Deny dialog
```

## Not built

brief-me §9 also planned a separate "Signal" calendar written from `life/`, on the narrower `calendar.app.created` scope. The tool now writes to the owner's own calendars instead, so that design isn't planned.

## Layout

`src/calendar_tool/` holds `auth/`, `google_api/`, `agenda/`, `changes/`, `service/`, `mcp_server/` and `cli/`, each with a README, plus `paths.py` and `errors.py`. cli and mcp_server use service; service uses changes, agenda and auth; changes uses agenda; all of them use google_api; everything uses errors. `schedule/` has the scheduled task scripts.

Dependencies:

- `google-auth`: credentials, refresh, `AuthorizedSession`.
- `requests`: the transport (same pin as mail).
- `mcp==2.3.0`: the MCP server (same pin as mail).
- `signal-googleauth`: `packages/googleauth`, the shared client file check, browser flow and DPAPI.
- `signal-jsonstate`: `packages/jsonstate`, the atomic JSON write for the cache.
- `signal-confirm`: `packages/confirm`, the owner's Allow/Deny dialog.
- `signal-untrusted`: `packages/untrusted`, the data frame around Google text in MCP results.

## Development

```
uv run --frozen pytest
uv run --frozen ruff check src tests
uv run --frozen ruff format src tests
```

The tests use a fake Calendar HTTP session, a fake dialog and a fake browser flow, and make no network calls. The sign-in and old-sign-in tests use real DPAPI and run on Windows only. The live sign-in and live writes are tested by hand.
