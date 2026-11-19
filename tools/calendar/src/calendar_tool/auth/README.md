# calendar_tool.auth

Google sign-in for the calendar tool. The generic parts (client file check, browser flow, credentials, DPAPI, atomic owner-only write) come from `packages/googleauth`, shared with `tools/mail`.

## Public API

- `SCOPES`: exactly `calendar.events` (`WRITE_SCOPE`) and `calendar.calendarlist.readonly`. `LEGACY_SCOPES`: the read-only pair a sign-in saved by the old read-only tool holds.
- `sign_in((client_path, token_path), expected_email) -> str`: runs the browser flow for `SCOPES` (all must be granted), checks the signed-in address (the primary calendar's id) against `expected_email`, and saves the token with its scopes only when it matches.
- `open_client(client_path, token_path) -> CalendarClient`: refreshes with the scopes the sign-in was granted, so an old read-only sign-in keeps reading, and sets `can_write` only when they include `WRITE_SCOPE`. Raises `SetupError` (no client file, not signed in) or `ReauthRequired` (token won't decrypt).
- `load_client(client_path)`: the shared client check, failures as `SetupError`.
- `StoredSignIn(email, refresh_token, scopes)`, `save_sign_in(path, sign_in)`, `load_sign_in(path)`: the one `.state/token.bin`, DPAPI-encrypted with calendar-only entropy. A file without `scopes` reads as `LEGACY_SCOPES`. `repr()` leaves out the token.

## Files

`scopes.py`, `session.py` (`open_client`, `load_client`), `sign_in.py`, `token_file.py`.

## Depends on

`signal_googleauth`, `google-auth`, `calendar_tool.google_api` (the client, and to look up the address) and `calendar_tool.errors`.
