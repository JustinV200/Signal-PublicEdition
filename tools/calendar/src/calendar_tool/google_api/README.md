# calendar_tool.google_api

The Google Calendar v3 REST client, over `google-auth`'s `AuthorizedSession` (no discovery client), and the calls the tool makes.

## Public API

- `CalendarClient(session, can_write=True)`: `get(path, params)` and `send(method, path, params, body, etag)` return the JSON object (`{}` for 204); `get_all_items(path, params)` follows `nextPageToken` (at most 20 pages).
  - A non-GET on a client without `can_write`, or Google's 403 for a missing scope, is `ReauthRequired` ("read-only ... Re-run `calendar add`"), raised before any request in the first case.
  - A refresh failure becomes `ReauthRequired` (`invalid_grant`, `invalid_scope`) or a code-only `CalendarError`, a network failure `OfflineError`, an error status `ApiError` (a 412 from `If-Match` says the event changed). Library exceptions never ride along (`from None`).
- Reads: `primary_calendar_email(client)`; `list_selected_calendars(client) -> list[CalendarInfo]` (the calendars ticked in Google Calendar's sidebar, named by `summaryOverride` or `summary`); `list_events(client, calendar_id, start, end)` (raw events, `singleEvents=true`); `calendar_entry(client, calendar_id) -> CalendarEntry` (id, name, and `is_writable` for the owner and writer roles); `get_event(client, EventAddress)`.
- Writes: `insert_event(client, calendar_id, body)`, `patch_event(client, address, body, send_updates="none")`, `delete_event(client, address)`. Insert and delete always send `sendUpdates=none`; patch and delete send the address's etag as `If-Match`.
- `EventAddress(calendar_id, event_id, etag=None)`: where an event lives, and the etag it was read with.
- Event facts: `marker_properties()` and `is_tool_event(raw)` (the private `signal=1` marker), `is_recurring(raw)`, `has_guests(raw)` (anyone besides the owner, judged without addresses), `own_attendee(raw)` and `invite_response(raw)` (the owner's own entry when someone else organises the event).

Every request sets `fields`. Lists get the id, status, title, times, the repeat link, `organizer/self`, attendees' `self` and response (no addresses) and the private properties; single reads add `etag`, `recurrence`, `attendeesOmitted` and attendee addresses (a reply must name the owner's own). With two or more attendees, `maxAttendees=1` makes Google return only the owner's entry. With exactly one attendee Google returns that entry whoever it is, so on a single read another person's address can reach this process; nothing shows or stores it, since only the owner's own entry is used.

## Files

`client.py`, `resources.py` (the list reads), `events.py` (the single-event calls), `event_facts.py`.

## Depends on

`requests`, `google-auth` and `calendar_tool.errors`.
