# signal_googleauth (packages/googleauth)

Google OAuth plumbing for `tools/calendar`, built to be shared with `tools/mail`. Both use the one Desktop-app OAuth client at `tools/mail/.state/google_client.json` and keep their own DPAPI-encrypted refresh tokens.

## Public API (`from signal_googleauth import ...`)

- `load_client_config(path) -> ClientConfig`: reads the Desktop-app client JSON and checks it. Raises `ClientFileError` for a missing file, a Web client, missing fields, or a non-Google `token_uri`. It never echoes the file. `ClientConfig`'s `repr()` leaves out the secret.
- `run_browser_flow(client_path, scopes, login_hint, success_message) -> Credentials`: the installed-app flow in the default browser, on `127.0.0.1` (random port, 5 min timeout, `prompt=consent`). Cancel, timeout or partly granted scopes raise `SignInError`.
- `build_credentials(refresh_token, client, scopes) -> Credentials`: google-auth refreshes the access token, which stays in memory only.
- `protect(secret, entropy)` / `unprotect(blob, entropy)`: Windows DPAPI, CurrentUser scope. Each tool passes its own entropy so blobs can't be swapped between tools. Failures raise `DpapiError`.
- `write_secret_atomically(path, blob)`: temp file in the same folder, locked to the owner with icacls (inheritance removed) before the bytes go in, fsynced, then `os.replace`d.
- `GoogleAuthError`: base of `ClientFileError` and `SignInError`. Messages are safe to show; library errors are replaced (`from None`) because they can carry token responses.

Each tool maps these errors onto its own (e.g. mail's `SetupError` and `AccountError`).

## Files

- `client_config.py`, `browser_flow.py`, `credentials.py`: the OAuth client, sign-in and credentials.
- `dpapi.py`: CryptProtectData/CryptUnprotectData via ctypes (originally from `tools/vault`).
- `owner_acl.py`: `restrict_to_owner`, the icacls sequence (originally from `tools/sessions`).
- `secret_file.py`: the atomic owner-only write.
- `errors.py`: the error types.

TODO: `tools/mail` still has its own copies of these files; a separate change moves it onto this package. `tools/vault` and `tools/sessions` still keep their own copies of `dpapi.py` and the icacls sequence; move them here when either is next touched.

## Depends on

`google-auth` and `google-auth-oauthlib` (same pins as the tools). Add it with `uv add --editable ../../packages/googleauth`.

## Tests

`uv run --frozen pytest` (the DPAPI/ACL test runs on Windows only).
