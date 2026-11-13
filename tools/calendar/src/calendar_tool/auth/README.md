# calendar_tool.auth

Google sign-in for the calendar tool. The generic parts (client file check, browser flow, credentials, DPAPI, atomic owner-only write) come from `packages/googleauth`, shared with `tools/mail`.

## Public API

- `SCOPES`: exactly `calendar.events.readonly` and `calendar.calendarlist.readonly`.
- `sign_in((client_path, token_path), expected_email) -> str`: runs the browser flow for `SCOPES`, checks the signed-in address (the primary calendar's id) against `expected_email`, and saves the token only when it matches.
- `open_session(client_path, token_path) -> AuthorizedSession`: raises `SetupError` (no client file, not signed in) or `ReauthRequired` (token won't decrypt).
- `load_client(client_path)`: the shared client check, failures as `SetupError`.
- `StoredSignIn(email, refresh_token)`, `save_sign_in(path, sign_in)`, `load_sign_in(path)`: the one `.state/token.bin`, DPAPI-encrypted with calendar-only entropy. `repr()` leaves out the token.

## Depends on

`signal_googleauth`, `google-auth`, `calendar_tool.google_api` (to look up the address) and `calendar_tool.errors`.
