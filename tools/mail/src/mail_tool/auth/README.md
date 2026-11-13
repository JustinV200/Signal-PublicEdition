# mail_tool.auth

Google sign-in for the mail tool: the OAuth client file, encrypted refresh tokens, and self-refreshing HTTP sessions.

## Public API

- `load_client_config(path) -> ClientConfig`: reads the Desktop-app client JSON and checks it. Raises `SetupError` for a missing file, a Web client, missing fields, or a non-Google `token_uri`. It never echoes the file.
- `TokenStore(folder)`: `save`, `load`, `find` (alias or email), `remove` and `aliases`. Each account is `<alias>.bin`, which holds `{"email", "refresh_token"}` encrypted with DPAPI (CurrentUser, with tool-specific entropy). Each save writes a temp file in the same folder, locks it to the owner with icacls, writes the blob, fsyncs, and `os.replace`s it into place. A crash leaves the old file or the new one, and the final file keeps the owner-only ACL. A blob that won't decrypt raises `ReauthRequired`.
- `AccountRecord(alias, email, refresh_token)`: its `repr()` leaves out the token.
- `normalize_alias(alias)`: lower-cases the alias and accepts only `[a-z0-9][a-z0-9_-]{0,31}`, since aliases become file names.
- `SCOPES`: `gmail.readonly` and `gmail.compose`.
- `GoogleSessions(client_path)`: called with a record, it returns a cached `AuthorizedSession`. google-auth refreshes the access token, which stays in memory only.
- `run_browser_flow(client_path, login_hint) -> Credentials`: the installed-app flow on `127.0.0.1` (random port, 5 min timeout, `prompt=consent`, with `login_hint`). Cancel, timeout or partly granted scopes raise `AccountError`.

## Files

- `client_secrets.py`: the client JSON.
- `token_store.py`: the encrypted per-account files.
- `dpapi.py`: CryptProtectData/CryptUnprotectData via ctypes (copied from `tools/vault`).
- `owner_acl.py`: `restrict_to_owner`, the owner-only icacls sequence (copied from `tools/sessions`).
- `sessions.py`: credentials and `AuthorizedSession`s.
- `browser_flow.py`: the sign-in flow.

## Depends on

`google-auth`, `google-auth-oauthlib`, and `mail_tool.errors`.
