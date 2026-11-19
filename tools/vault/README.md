# vault

> **SECURITY-SENSITIVE: changes to this tool need the owner's review.**
> Agents can edit everything in `tools/vault`, and this code is what stands
> between an agent and the owner's passwords. Any change here (origin checks,
> field choice, exception handling, crypto, unlock, confirmation, the CLI's TTY
> check) must be reviewed by the owner before it's used with real credentials.
> An agent should never weaken a check to make a task work.

Local credential vault that logs Claude Code agents into the owner's accounts
**without any secret reaching the model**: not in tool results, logs,
exceptions or tracebacks. Design: `refdocs/research/password-vault.md`
(Option B, section 5 v1 defaults, and its "Implementation notes").

## Public API

`tools/browser` imports these in-process (`from vault import ...`):

```python
list_credentials() -> list[CredentialInfo]   # id, name, origins, username_hint only
async fill_login(page, credential_id, *, submit=False) -> FillResult   # FillResult(ok, reason)
async has_filled_fields(page) -> bool        # browser must block snapshot/screenshot while True
scrub(page, text) -> str                     # removes filled usernames/passwords from outbound text
```

There is no API that returns a secret. `FillResult.reason` is one of `filled`,
`origin_mismatch`, `denied`, `locked`, `no_fields`, `not_found`, `tampered`,
`unsafe_environment`, `error` (see `vault/models.py`).

### What a fill does

1. Refuses if `DEBUG`, `DEBUG_FILE` or `PWDEBUG` is set at all (Playwright debug
   wildcards log fill values).
2. Finds exactly one visible `input[type=password]` across all frames, ignoring
   `autocomplete=new-password` fields in other forms, plus the username field in
   the same form. Refuses if that field's form (or root node, with no form) holds
   a `new-password` field, since that's a change-password form.
3. Checks the top-level origin and every frame from the field up to the top
   against the credential's registered origins: exact https scheme + host +
   port. about:blank, srcdoc, data: and blob: frames never match.
4. Asks the owner in a topmost Allow/Deny dialog (the shared `signal_confirm`,
   `packages/confirm`) showing the credential name and the live origin. Deny is
   the default, Allow has no keyboard shortcut, and it denies by itself after 60 s.
   Skipped for a credential whose policy is `confirm=never` (see Owner CLI).
5. Unlocks (Windows Hello prompt, or the passphrase dialog), unwraps the data
   key, decrypts this one record (AES-GCM; its AAD binds the origins), wipes the keys.
6. Re-checks origins on the same `ElementHandle`s and fills through them (a
   navigation in between makes the fill fail instead of landing on the new page).
7. Writes one audit line and returns a bare `FillResult`. Any exception,
   including Playwright's (which quote `fill("<value>")`), becomes
   `FillResult(False, "error")` and is never logged or re-raised.

## Owner CLI

Run these **yourself, in Windows Terminal, PowerShell or cmd** (not Git Bash,
which native Python sees as a pipe, and never through Claude Code):

```
uv run --project tools/vault vault init                      # Windows Hello (default)
uv run --project tools/vault vault init --unlock passphrase  # explicit fallback
uv run --project tools/vault vault add github --name GitHub --origin https://github.com
uv run --project tools/vault vault add github --name GitHub --origin https://github.com --username me
uv run --project tools/vault vault list
uv run --project tools/vault vault remove github
uv run --project tools/vault vault policy github --confirm never   # or: always
```

- `init` with Hello prompts three times (create the key, then sign twice to
  check signatures are deterministic). If Hello isn't available it fails; it
  never switches to the passphrase by itself.
- `add`, `init`, `remove` and `policy` refuse unless stdin is an interactive terminal.
  `add` reads the username and password twice each with `getpass`, warns about
  excluded account kinds (email, SSO, financial, password managers,
  DNS/cloud, government/health, admin/recovery), and unlocks to save.
- `policy ID --confirm always|never` sets whether fills of that credential show
  the Allow/Deny dialog (default `always`; any unknown value also asks). It
  unlocks and re-keys the whole vault (like `remove`), since the policy is
  bound into each record's ciphertext: hand-editing store.json just breaks the
  record, and a saved copy of the record from before the change stops
  decrypting, so an agent can't switch it or roll it back. As with `remove`,
  a full copy of the old store.json still opens with the same unlock factor.
  **`never` leaves Windows Hello (or the passphrase) as the only owner gate
  for that credential.** Origin checks, the re-check before the fill and the
  audit log are unchanged; an auto-approved fill is logged with
  `"confirm": "auto"`.
- `remove` unlocks and re-seals the remaining credentials under a fresh data
  key, so the removed record pasted back alone no longer decrypts. The unlock
  factor doesn't change, though, so a full copy of the old store.json (or its
  old `wrapped_dek` pasted back) still opens with the same Hello key or
  passphrase. Removal is not a full revocation; change the site password too.
- `--username` skips the username prompt (usernames aren't secret). The password
  is always prompted: `--password`, `--pass`, `-p` and `--pw` are refused before
  parsing so a password never lands in shell history or error output.
- `--origin` given as a full https URL is cut down to its origin ("using origin ...").
- Internationalised hosts must be given in punycode (`xn--...`).
- There is no show/export command.

## Files

`%LOCALAPPDATA%\signal-vault\store.json` (ciphertext + metadata) and
`audit.jsonl` (timestamp, event, credential id, origins, result; never secrets).
Both are outside the repo.

## Layout

| Package | Purpose |
|---|---|
| `vault/api.py`, `models.py` | The public functions and result types |
| `vault/origin.py` | Origin parsing and exact matching |
| `vault/crypto/` | AES-GCM, HKDF, scrypt (explicit `maxmem`), DPAPI (ctypes), canonical AAD, wiping |
| `vault/store/` | store.json schema, codec, key hierarchy (KEK wraps DEK), record sealing |
| `vault/unlock/` | `Unlocker` interface; Windows Hello (`KeyCredentialManager`) and passphrase + DPAPI |
| `vault/confirm/` | `Confirmer` interface; Allow/Deny dialog confirmer via `signal_confirm` (audiohub voice can be added here) |
| `vault/fill/` | Field finding, origin checks, the leak-proof fill step, snapshot gate, scrubber |
| `vault/cli/` | Owner-only `vault` command |
| `vault/audit.py`, `secret.py`, `paths.py` | Audit log, redacting `Secret` wrapper, data paths |

Dependencies: `cryptography` (AES-GCM, HKDF; the stdlib has neither) and
pywinrt `winrt-*` 3.2.1 (Windows Hello). DPAPI and the passphrase dialog use
the stdlib (ctypes, tkinter). The fill confirmation comes from `signal_confirm`
(`packages/confirm`, stdlib only). Playwright is a dev dependency only; the
vault never imports it.

## Known limits

- **Windows Hello is untested end to end.** The owner wasn't available, so
  `unlock/hello_winrt.py` has only had `is_supported_async()` run on this
  machine. Before real use, the owner should run `vault init`, `vault add` and
  one fill, and confirm the prompt appears and a second fill unlocks.
- Same-user code (the agent's own shell) can still click the confirmation box,
  read process memory during a fill, or read the browser's DOM. The human
  factor (Hello or passphrase) is the gate. See the threat model in the design doc.
- Filled values stay in this process's memory (inside `Secret`) while the
  page is open, so `scrub` can catch them. Python can't wipe strings.
- TODO: username-first logins (no password field on the first page) return
  `no_fields`; v1 needs both on one page, or a password-only page.

## Tests

```
uv run pytest                 # headless Edge (channel msedge), no browser download
```
