# server/security

- `guards.py`: `build_guard(auth, local_key)` is the middleware that checks Host, Origin, the page's session token or the local key. `add_security_headers` sets CSP, nosniff, no-referrer and cache headers.
- `sessions.py`: `SessionAuth` issues and redeems one-time login keys (single use, 60 s), mints a session token per login (the newest `MAX_SESSIONS` are kept, in memory only) and checks the `X-Console-Token` header. `secrets_match` is the constant-time compare both checks use.

The page's credential is a header, never a cookie: browsers send 127.0.0.1 cookies to every port, so any local listener would get it.

Public API: `signal_console.server.security`. Depends on `aiohttp` and `local_api` (for the local route paths).
