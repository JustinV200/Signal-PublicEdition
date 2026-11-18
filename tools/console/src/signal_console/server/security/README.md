# server/security

- `guards.py`: `build_guard(auth, local_key)` is the middleware that checks Host, Origin, the page's session token or the local key. `add_security_headers` sets CSP, nosniff, no-referrer and cache headers. `signed_out_body(reason)` is every 401's body (the guard's `not signed in` and the login route's bad key): `{error, openCommand}`, the reason and the full `console open` line with this checkout's absolute path (`signal_console.open_hint`). It holds no key or token, and no CORS header is ever added, so only local processes can read it. `HTTP_UNAUTHORIZED` (401) is exported for the login route.
- `sessions.py`: `SessionAuth` issues and redeems one-time login keys (single use, 60 s), mints a session token per login (the newest `MAX_SESSIONS` are kept, as digests) and checks the `X-Console-Token` header. `secrets_match` is the constant-time compare both checks use. Given a digest file, it loads it when built and saves it on each login, so pages survive a restart.
- `token_digests.py`: the tokens' SHA-256 digests in `.state/session-digests.json`, never a token. The file is locked to the current user before each write; a failed lock fails the write (the login still works until the next restart).

The page's credential is a header, never a cookie: browsers send 127.0.0.1 cookies to every port, so any local listener would get it.

Public API: `signal_console.server.security`. Depends on `aiohttp`, `local_api` (for the local route paths), `open_hint` (the command line) and `state_files` (the owner-only digest file).
