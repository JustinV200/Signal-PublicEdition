# calendar_tool.google_api

The read-only Google Calendar v3 REST client, over `google-auth`'s `AuthorizedSession` (no discovery client).

## Public API

- `CalendarClient(session)`: `get(path, params)` returns the JSON object; `get_all_items(path, params)` follows `nextPageToken` (at most 20 pages). A refresh failure becomes `ReauthRequired` (for `invalid_grant`) or a code-only `CalendarError`, a network failure `OfflineError`, an error status `ApiError`. Library exceptions never ride along (`from None`).
- `primary_calendar_email(client)`: the signed-in address (the primary calendar's id).
- `list_selected_calendars(client) -> list[CalendarInfo]`: the calendars ticked in Google Calendar's sidebar, named by `summaryOverride` or `summary`.
- `list_events(client, calendar_id, start, end)`: raw events with `singleEvents=true`.

Every request sets `fields`, so only `id`/`summary`/`selected` and `status`/`summary`/`start`/`end` come back.

## Depends on

`requests`, `google-auth` and `calendar_tool.errors`.
