# browser_tool.cookie_store

The saved-cookies file: the desktop browser saves its cookies on a clean close and gets its session cookies back at the next launch, and visit mode (the checker) borrows the desktop's sign-in from it.

## Public API (`from browser_tool.cookie_store import ...`)

- `CookieMode.OWN` / `CookieMode.BORROW`, passed to `BrowserSession(cookie_mode=...)` (via `ActionContext.create`).
  - `OWN` (the desktop MCP server, `server/wiring.py`): `restore` adds back only session cookies, since the profile keeps its persistent ones (perhaps newer than the file); `save` writes every cookie.
  - `BORROW` (`visit/cli.py`): `restore` adds back every unexpired cookie; `save` does nothing.
- `CookieKeeper(path, policy, mode, clock=time.time)`: `async restore(context)` and `async save(context)`. Neither ever raises.
- `DPAPI_ENTROPY`: the blob's DPAPI entropy (tests).

## Rules

- File: `[browser] cookie_file` (default `tools/browser/.state/cookies.bin`, gitignored). JSON `{"version": 1, "cookies": [...]}`, encrypted with DPAPI (CurrentUser, with `DPAPI_ENTROPY`), written atomically through a temp file locked to the current user with `icacls` before the bytes go in. A failed ACL refuses the write.
- Saved: Playwright's cookie fields that `add_cookies` takes. Partitioned (CHIPS) cookies are left out, since restoring one would drop its partition.
- Restored: only from a file whose every cookie has the right fields and types (else the whole file is ignored), only unexpired ones, and only for a host the loading browser's own policy allows. A domain cookie (`.google.com`) also counts when an allowlisted host sits under it (`accounts.google.com`), because that host is sent it; for a `*.example.com` pattern the probe is `a.example.com`.
- Never logged: cookie names, values and domains. Log lines give counts and error types only.
- A missing file is silent; an unreadable, undecryptable (another user, other entropy) or malformed one is ignored with one warning.

## Files

`keeper.py` (the modes, restore and save), `cookie_filter.py` (pure: the saved shape and the restore filter), `secret_file.py` (owner-only atomic write), `dpapi.py` (ctypes DPAPI, copied from `packages/googleauth`, since tools stay standalone).

## Dependencies

`browser_tool.policy` (`HostPolicy`), `playwright`, and Windows (`crypt32`, `icacls`).
