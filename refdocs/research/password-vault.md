# Password vault: Claude logs in without seeing secrets

Researched 2026-10-19 for a future `tools/vault` package. Sources are inline. **[unverified]** marks claims from secondary sources, from fetches whose summary left the detail out, or my own untested inference.
This doc pairs with `browser-control.md`, which recommends a Python Playwright MCP server in `tools/browser` that calls the vault in-process through `fill_login`.

## 1. Existing options

| Option | How an agent uses it | Keeps the secret out of model context? |
|---|---|---|
| **1Password CLI** (`op`) | Secret references `op://vault/item/field`. `op read` prints to stdout. `op run` puts secrets in a child's env and masks them in its stdout/stderr. `op inject` fills templates. https://developer.1password.com/docs/cli/secret-references | **Only as a backend.** If Claude runs `op read` in Bash, the value lands in the transcript. `op run` masking is an output filter, and the child process (agent-controlled) still holds the value. It works well behind our broker (see Option A). |
| **1Password for Claude** (Secure Agentic Autofill) | Claude in Chrome asks the 1Password extension for a login. The owner approves the item, and it's filled "through a secure channel outside the agent's view", OTP included. Claude "only knows which login it used". Agentic Mode locks the extension to approved items. https://support.1password.com/1password-claude/ | **Best in class, but not usable here.** It needs "A Mac device", 1Password for Mac 8.12.28+, the Claude desktop app and Claude in Chrome. There is no Windows date. The March 2026 press release says Claude Code and Cowork support is coming https://1password.com/press/2026/mar/1password-unified-access **[Claude Code support unverified]**. It can't be hooked into our own Playwright tool. |
| **1Password SDK** (Python `DesktopAuth`) | A library authorized through a desktop-app prompt, valid for 10 minutes of inactivity. https://www.1password.dev/sdks/desktop-app-integrations | Backend only. Windows support is **[unverified]**: an earlier docs version said Mac/Linux until GA. |
| **Bitwarden CLI** (`bw`) | `bw unlock` returns a `BW_SESSION` key, and `bw get password` prints plaintext. | Backend only, and weak. `BW_SESSION` is a bearer token: any same-user process that holds it can read the whole vault, with no per-use biometric **[unverified for the CLI]**. |
| **Bitwarden MCP server** | Tools such as `get`, `list` and `generate` (TOTP) over `bw`. Needs Node 22+. https://github.com/bitwarden/mcp-server | **No.** The README says it can "Expose credentials and vault contents through AI responses". Bitwarden recommends a local self-hosted LLM with it https://bitwarden.com/blog/how-bitwarden-helps-secure-agentic-ai-access-to-your-credentials.md. Only `unlock` hides the master password. |
| **Bitwarden Agent Access** (`aac`) | A Noise-encrypted tunnel to a credential provider. `aac run` injects into a child's env. Rust core with Python bindings, and a Windows x86_64 build. https://github.com/bitwarden/agent-access | The design is right: with `aac run`, no plaintext reaches the model. But it's an "early preview" ("APIs and protocols are subject to change") and targets env vars, not web forms. Per-request approval isn't documented **[unverified]**. Worth watching. |
| **KeePassXC** | `keepassxc-cli show/clip` needs the database password on each call https://man.archlinux.org/man/keepassxc-cli.1.en. The browser protocol (NaCl box, `associate`, `get-logins` by URL, `get-totp`) is documented at https://github.com/keepassxreboot/keepassxc-browser/blob/develop/keepassxc-protocol.md | Backend only. In the browser protocol, the owner approves the association in the GUI and KeePassXC matches entries by URL. But `get-logins` returns plaintext to any associated client, and the Python client libraries are unvetted **[unverified]**. |
| **Windows Credential Manager** via `keyring` | `keyring.get_password(service, user)`. The Windows backend is the Credential Locker. https://pypi.org/project/keyring/ (25.7.0) | Backend only, and weak. Any process running as the owner can read it with no prompt. The keyring docs say "No analysis has been performed" for Windows. The same-user behavior is **[my inference from how Credential Manager works]**. |
| **Windows DPAPI** | `CryptProtectData`: "only a user with the same logon credential … can decrypt". Its prompt flow is deprecated and will be removed in February 2027. https://learn.microsoft.com/en-us/windows/win32/api/dpapi/nf-dpapi-cryptprotectdata | Encryption at rest that protects against other users and offline disk theft. Any same-user process can call `CryptUnprotectData`, and there is no human gate. |
| **Windows Hello key** (`KeyCredentialManager`) | A TPM-backed key signs a challenge after a face/PIN prompt, and a hash of the signature becomes an AES key. KeePassXC quick unlock does this (PR #7384) https://github.com/keepassxreboot/keepassxc/pull/7384 | A **human gate the agent can't pass**. pywinrt publishes `winrt-Windows.Security.Credentials` 3.2.1 with cp312 win_amd64 wheels (checked on PyPI), so the import works on Python 3.12. Whether the prompt shows, takes focus and signs deterministically from an unpackaged `python.exe` still **needs a spike** (corrected in review). The HWND interop call applies to `UserConsentVerifier` https://learn.microsoft.com/en-us/windows/win32/api/userconsentverifierinterop/nf-userconsentverifierinterop-iuserconsentverifierinterop-requestverificationforwindowasync. KeePassXC's `KeyCredentialManager` path doesn't use it. It brings the prompt forward with `FindWindowA("Credential Dialog Xaml Host")` + `SetForegroundWindow`, and it keeps the wrapped key in memory only, never on disk (corrected in review; https://github.com/keepassxreboot/keepassxc/blob/develop/src/quickunlock/WindowsHello.cpp). |
| **Agent secret brokers** (2026) | Infisical Agent Vault is an HTTP proxy that injects API auth headers https://github.com/Infisical/agent-vault. browser-use `sensitive_data` uses placeholder names and per-domain secrets with vision off https://docs.browser-use.com/customize/examples/sensitive-data. OAuth token vaults: Arcade, Nango, Auth0 (survey: https://flaviocopes.com/ai-agent-passwords/). | API-key proxies and OAuth vaults keep secrets out well, but they don't fill web-form logins. browser-use's pattern is the model to copy. It once had an `allowed_domains` bypass through a decoy domain in the URL's userinfo, fixed in 0.1.45 **[secondary source: https://mcp.depscope.dev/bugs/pypi/browser-use]**. |

**Takeaway:** nothing off the shelf fills a web login on Windows from a Python Playwright tool with domain binding and a human gate. We build a thin broker, and the only open choice is where the ciphertext lives.

## 2. Threat model

Assumptions: one Windows user account, and Claude Code on native Windows, where "Claude Code runs commands unsandboxed" (https://code.claude.com/docs/en/sandboxing). MCP servers run outside the sandbox on any OS. So **Claude's Bash has the owner's full rights.**

| Threat | Example | Mitigation | What's left |
|---|---|---|---|
| Injection makes the agent fill on a phishing domain | The page says "re-login at github-login.example"; the model calls `fill_login("github")` there. | The vault, not the model, checks both the top-level origin and the origin of the frame that holds the password field against the credential's registered origins. Matching is exact scheme+host+port, https only, IDNA-normalized, rejects userinfo, and allows no wildcards by default. The check runs again just before the fill (navigation race). Origins are bound into the ciphertext AAD, so editing the metadata breaks decryption (Option B). | A compromised or XSS'd legitimate origin, or an origin the owner registered too broadly. |
| Secret typed into a visible field, then read back | The model aims the password at a search box or comment field, then snapshots or screenshots the page. | The model never supplies selectors. The vault finds the fields itself and puts the password only into `input[type=password]` in the matched frame. Snapshots never return the value of a password input or a vault-filled input. Screenshots pass those locators to Playwright `mask=` (in Playwright since before 1.35, which added `mask_color`: https://newreleases.io/project/pypi/playwright/release/1.35.0). Outbound tool text is scrubbed for the exact secrets filled on that page. There is no `evaluate`/run-JS tool. | Page JS can copy the value into visible text in a form we don't scrub (for example, reversed). The masking is untested **[unverified]**. Playwright does **not** hide passwords in snapshots. In the installed 1.64.0, `aria_snapshot` emits `element.value` for every `input` except checkbox, radio and file, and `type=password` maps to `textbox`. So a post-fill snapshot prints the plaintext unless our tool blocks it (corrected in review: checked in `playwright/driver/package/lib/coreBundle.js`). |
| Injection reaches management | "Add evil.com to github's origins" or "export the vault". | No MCP tool can add, edit or reveal. Management is an owner-run CLI that refuses non-TTY stdin and requires Windows Hello. There are no `show`/`export` commands at all. | The agent can still try through Bash, which raises a Hello prompt the owner must deny. |
| Leaks through results, logs or crashes | Exception messages, debug logs, Playwright traces, MCP stderr that Claude Code captures, transcripts in `~/.claude/projects/*.jsonl`. | A `Secret` wrapper with a redacted `repr` that can't be pickled. Plaintext is unwrapped only inside the fill call. Fill errors are re-raised as `VaultFillError(reason) from None`. No tracing and no `DEBUG=pw:api` on vault contexts (traces likely record fill values **[unverified]**). Secrets never go in argv or env. The audit log holds ids and origins only. | Python can't wipe strings, so a full crash dump of the server process could contain them. Playwright 1.64 writes `fill("<value>")` into the action's call log, and that call log goes into error messages (for example, timeouts). So a raw fill exception carries the plaintext. Also, `raise ... from None` only hides `__context__`; the original exception, with its message and frames, stays attached. Catch everything inside the vault and return a bare `FillResult`; never re-raise (corrected in review). |
| Another local process | Malware, or the agent's own Bash, reads the store, calls DPAPI, imports vault internals, or reads the server's memory. | The store key is wrapped by Windows Hello, so silent offline decryption is impossible. Unlock windows are short (10 min idle, 1 h max by default). High-value credentials require Hello on every use. | **During an unlock window, any same-user process can read the server's memory.** The real fix is the hardening step in section 3. |
| Spoofed approval | A process shows a fake "approve GitHub?" prompt, or plays "yes" through the speakers to audiohub. | Hello is authentication (face/PIN). A voice or dialog yes/no is only intent confirmation, and the vault runs it directly, never relayed by the model. | The caller chooses the Hello prompt text, so the owner approves "a prompt", not provably "this fill". |
| 2FA/TOTP | With both the password and the TOTP seed, the agent owns the account alone. | Default: **no TOTP seeds in the vault.** The owner does 2FA: a phone push, or typing the code into the headed browser while the tool waits. A low-value credential can opt in to `totp`: the code is generated in-process (stdlib `hmac`, RFC 6238), filled like the password, and never returned. Codes are never dictated by voice, because the transcript would hold them. Passkeys need a human gesture and stay manual. | An opted-in seed collapses 2FA into one factor that sits next to the password. |
| After login | The session cookie in the automation profile gives the agent the whole account. | Outside the vault's scope: the browser tool's allowlist and action gates handle it. Keep email, banking and the password manager out of the vault entirely. | This is the largest remaining risk. |

**What the "Claude never sees it" guarantee covers, for the designed tool paths:**
- No tool the model can call returns a password, a username (it gets only a hint) or an OTP. So these never reach the context, the transcript, API traffic to Anthropic, or our logs.
- A credential fills only on its registered origins, whatever the model asks.
- At rest, the store can't be decrypted without the owner's Windows Hello gesture, and every unlock and fill is audited.

**What it doesn't cover:**
- An agent misbehaving through its shell during an unlock window, or malware running as the owner. "Never sees it" means no designed path shows the secret, not that Claude *cannot* get it.
- What the agent does once logged in, and logins on a compromised legitimate site.
- Bugs in our own unaudited redaction and origin code.

## 3. Architecture for `tools/vault`

**Shared core (both options):**

```
tools/vault/src/vault/
  __init__.py   public API only: list_credentials, fill_login, fill_totp, CredentialInfo, FillResult
  origin.py     parse and match origins (IDNA, https, exact host+port, no userinfo)
  fields.py     find username / password / OTP inputs in a frame
  fill.py       the fill sequence below
  secret.py     Secret wrapper (redacted repr, no pickling)
  audit.py      hash-chained JSONL, no secrets
  approval/     policy.py, hello.py, voice.py (audiohub), dialog.py (tkinter)
  backends/     base.py (SecretBackend protocol), local_store.py (B), onepassword.py (A)
  cli/          owner-only: add, list, remove, set-origins, rotate, lock, audit
```

```python
@dataclass(frozen=True)
class CredentialInfo:   # safe to show the model
    id: str; label: str; origins: tuple[str, ...]; username_hint: str; has_totp: bool
@dataclass(frozen=True)
class FillResult:       # reason: filled|origin_mismatch|denied|locked|no_fields|not_found|error
    ok: bool; reason: str
def list_credentials() -> list[CredentialInfo]: ...
async def fill_login(page: PageLike, credential_id: str, *, submit: bool = False) -> FillResult: ...
async def fill_totp(page: PageLike, credential_id: str) -> FillResult: ...
# There is deliberately no get_secret / reveal / export in the public API.
```

- `tools/browser` wraps these as the MCP tools `vault_list()`, `fill_login(credential_id, submit)` and `fill_totp(credential_id)`. It returns text such as `filled github on https://github.com`.
- Dependencies point one way, browser → vault. `PageLike` is a small Protocol, so the vault doesn't import Playwright.
- `fill_login` sequence:
  1. Load metadata without decrypting.
  2. Find the password input, searching frames too. Check the top-level origin and the frame origin; if either fails, return `origin_mismatch`.
  3. Run the approval policy: per credential, `confirm=always|session` (a voice or dialog prompt such as "Sign in to github.com as j***?") and `hello=unlock|each_use`.
  4. Get the secret from the backend, prompting for Hello if locked.
  5. Re-check the origins, then `locator.fill`. Register the filled elements and values with the browser's redaction hook, and submit if asked.
  6. Drop the references, write the audit record, return a `FillResult`.
- Audit record: `ts, event, credential_id, top_origin, frame_origin, decision, reason, approver, caller_pid, prev_hash`. It stores origins only, never full URLs, because query strings carry tokens. The file is `%LOCALAPPDATA%\signal-vault\audit.jsonl`, outside the repo.
- Voice approval: the vault calls an audiohub confirm endpoint directly. audiohub is still a stub (`tools/audiohub/src/audiohub/__init__.py`), so that endpoint has to be designed.

### Option A: backed by a password manager (1Password `op`)

- Agent credentials live in a dedicated 1Password vault named `Agent`. A local config maps each id to `op://Agent/<item>`. Allowed origins come from the item's website field, so widening them means editing the item, which needs the owner.
- The backend runs `op read` through `subprocess.run(capture_output=True)` and keeps stdout in memory. TOTP is `op read "op://Agent/GitHub/one-time password?attribute=otp"` (syntax from the secret-references page).
- Hello app integration: on Windows, "commands executed in a sub-shell require separate authorization". The session is keyed to the invoking PID, lasts 10 min idle with a 12 h hard limit, and is revoked when the app locks (https://www.1password.dev/cli/app-integration-security/). So `op` run from Claude's own Bash triggers its own Hello prompt.
- The owner adds and rotates items in the 1Password app as usual. No custom add CLI is needed.
- **Pros:**
  - Audited encryption, plus sync and backups.
  - One source of truth.
  - A Hello gate.
  - A path to first-party 1Password for Claude once it reaches Windows.
- **Cons:**
  - Needs a 1Password plan and an `op` install.
  - App-integration auth covers the whole account, so a compromised server can read *any* item for 10 minutes.
  - The Bitwarden and KeePassXC equivalents are weaker (see section 1).

### Option B: self-contained store

- `%LOCALAPPDATA%\signal-vault\store.json` holds one record per credential: `{id, label, origins, username_hint, policy, nonce, ciphertext}`. The ciphertext is AES-256-GCM over `{username, password, totp_seed?}`, with AAD = `id + origins + policy`, so any tampering makes decryption fail.
- The data key is wrapped by a Windows Hello key: sign a fixed challenge with a `KeyCredentialManager` key, then SHA-256 the signature into a KEK (the KeePassXC approach, which depends on deterministic signatures **[unverified from Python]**). If the spike fails, the fallback is KEK = `hashlib.scrypt(passphrase)` from a tkinter dialog, with DPAPI wrapping on top.
- Dependencies:
  - `cryptography`, for AES-GCM, which the stdlib lacks.
  - pywinrt `winrt-runtime`, `winrt-Windows.Security.Credentials`, `winrt-Windows.Security.Cryptography`, `winrt-Windows.Storage.Streams` and `winrt-Windows.Foundation`, all 3.2.1 with cp312 wheels (corrected in review: names verified on PyPI).
  - TOTP needs only the stdlib.
- Adding a credential: the owner runs `uv run --project tools/vault vault add github --origin https://github.com` in their own terminal, never in Claude Code's `!` prompt and never at Claude's request.
  - The username and password are read with `getpass` (hidden) and entered twice.
  - The command refuses non-TTY stdin and asks for Hello to save.
  - It prints only `added github`.
- **Pros:**
  - Least privilege: the store holds only what the owner put in.
  - No subscription and no Node.
  - Works whatever the owner's password manager turns out to be.
  - Origins are tamper-bound.
- **Cons:**
  - The crypto glue is ours (it uses `cryptography`'s AES-GCM, nothing custom).
  - Passwords are duplicated, so they must be rotated in two places.
  - No sync.
  - Losing the Hello/TPM key means re-adding every credential.

### Recommendation: Option B, behind the `SecretBackend` interface

- All the agent-facing safety (origin binding, field choice, redaction, approval, audit) is our code in either option. The backend only decides encryption at rest.
- B limits the blast radius to the few credentials the owner adds. It works today with no new account, and AAD stops metadata tampering.
- If the owner already lives in 1Password and dislikes the duplication, make A the default backend instead. The public API doesn't change.
- **Build order:**
  1. `origin.py` and its tests (IDNA, userinfo, ports, subdomains, redirects).
  2. The local store and the CLI.
  3. The Hello spike.
  4. Fill and redaction, together with `tools/browser`.
  5. The approval channels.
  6. The audit log.
- **Hardening (later):** this step turns the same-user limit into a real boundary.
  - Run the browser+vault MCP server as a separate standard Windows account, so non-elevated owner processes can't open its memory **[the cross-account stdio/named-pipe hand-off is unverified]**.
  - Or run Claude Code in WSL2 with the sandbox and `denyRead` on the vault paths (sandboxing docs above).
  - Either way, add Claude Code deny rules or a PreToolUse hook for `vault`, `op`, `bw`, `keepassxc-cli` and the vault folder. That's a speed bump, not a boundary.

## 4. Owner decisions

1. **Which password manager do you use, if any?** With 1Password, Option A is just as good with less code. With anything else, or none, use Option B.
2. **Which accounts go in?** I suggest leaving out email, banking, the password manager itself, and anything that can reset other accounts.
3. **Is Windows Hello set up** (PIN, face or fingerprint)? Option B's unlock depends on it.
4. **Approval policy:** one Hello per unlock window (10 min idle) or one per use? And do you want a voice yes/no before each fill?
5. **TOTP:** keep 2FA with you (recommended), or opt in specific low-value accounts?
6. **May Claude see usernames,** or only a hint such as `u***@gmail.com`?
7. **Accept the same-user limit** for now, or plan the hardening step (a separate account or WSL2)?
8. **Confirm a dedicated automation browser profile** (see `browser-control.md`). It holds the session cookies, which are the post-login risk.

## 5. v1 defaults (decided in review)

The owner was away, so these are the conservative picks. The owner can loosen them later.

| Question | v1 default | Reason |
|---|---|---|
| Backend | Option B, the local store | No password manager is confirmed, and B holds only what the owner adds. |
| Unlock | A Hello `KeyCredential` signs a random per-vault challenge. HKDF-SHA256 turns the signature into the KEK, which AES-GCM-wraps the DEK. **Fallback:** the KEK is `hashlib.scrypt` of a passphrase typed into a native dialog, and DPAPI wraps the file. `vault init` records which one is used. There is never a silent downgrade. | DPAPI alone plus a confirm dialog gives no gate against same-user Bash: it can call `CryptUnprotectData`, re-encrypt with new AAD, or click the dialog. A human secret is the only thing that keeps the gate. |
| Unlock window | None. Unlock on every fill, and overwrite the DEK `bytearray` afterwards. | This removes the memory-read-during-window gap. Logins are rare, and the owner is present for 2FA anyway. |
| Per-fill confirmation | Always. A native system-modal dialog from the vault process shows the label and the live origin. It defaults to No and denies after 60 s. Voice is off until audiohub has a real endpoint. | The model never relays the approval. The Hello prompt alone doesn't say what is being filled. |
| TOTP | Off. Store no seeds and don't expose `fill_totp` as an MCP tool. | Keeps two factors. |
| Usernames | Hint only, and they are blocked and scrubbed like passwords. | A filled username shows up in snapshots otherwise. |
| Excluded | Email, SSO/identity (Google, Microsoft, Apple), banking/brokerage/payments/crypto, password managers, registrar/DNS/cloud consoles, government/health/tax, and any admin or account-recovery account. | These can reset or drain other accounts. |

**Build rules from the review:**
- AAD is canonical JSON (`sort_keys`, fixed separators) over every metadata field plus the format version and the unlock provider. Build it from the same in-memory record that the origin check uses.
- Each encryption gets a fresh `os.urandom(12)` nonce. The DEK is `AESGCM.generate_key(256)`.
- After the origin check, take an `ElementHandle` and fill through it. A `Locator` re-resolves after a navigation and would fill the new page. Re-check `handle.owner_frame()` and the top-level origin, then call `handle.fill(..., timeout=5000)`.
- A frame whose URL is `about:blank`, `about:srcdoc`, `data:` or `blob:` is an origin mismatch. Require exactly one visible password input. More than one, or `autocomplete=new-password`, returns `no_fields`.
- Disable password saving in the automation profile. Never enable tracing, HAR or video on the context. Strip `DEBUG` and `PWDEBUG` at server start. The route handler never logs `post_data`.
- While any vault-filled or non-empty password input is connected, `snapshot()` and `screenshot()` refuse. As a backstop, all outbound text passes through `vault.scrub`.

**Public interface for `tools/browser`** (supersedes the `vault.resolve` sketch in `browser-control.md`):

```python
from vault import list_credentials, fill_login, has_filled_fields, scrub, CredentialInfo, FillResult
list_credentials() -> list[CredentialInfo]
async fill_login(page: playwright.async_api.Page, credential_id: str, *, submit: bool = False) -> FillResult
async has_filled_fields(page) -> bool   # True blocks snapshot and screenshot
scrub(page, text: str) -> str           # exact-match backstop; plaintext stays inside the vault
```

## Implementation notes (from security review)

Built in `tools/vault` (see its README). How the binding review points landed:

1. **Origin race:** the fill goes through the `ElementHandle` that passed the check, never a `Locator`. Origins are re-checked right before `handle.fill`. Exactly one visible password input is required across all frames, and `new-password` fields are refused.
2. **Frames:** the top-level page and every frame from the field up to the top must match exactly (https, ASCII host, port; non-ASCII hosts must be registered in punycode, because Python's `idna` codec is IDNA2003). about:blank, srcdoc, data: and blob: frames have no https origin, so they never match.
3. **Exceptions:** `fill/safe_fill.py` is the only code that hands plaintext to Playwright. It discards every exception unlogged and returns False. A cancellation is re-raised as a fresh `CancelledError` outside the except block, so it has no `__context__`. The sequence maps any other error to `FillResult(False, "error")`.
4. **Crypto:** a KEK wraps a random 256-bit DEK, and the DEK seals each credential with AES-GCM and a fresh 12-byte nonce. Record AAD is canonical JSON of `{id, name, origins, policy, provider, username_hint, version}`. The wrapped-DEK AAD covers the header (challenge, provider, unlock params, version). The per-vault 32-byte challenge salts HKDF-SHA256. scrypt uses an explicit `maxmem` and bounds-checked parameters.
5. **Unlock:** every fill unlocks, and the KEK and DEK bytearrays are wiped afterwards. Hello: `KeyCredential` signs the challenge, then HKDF. `init` signs twice and refuses if the signatures differ. Passphrase (an explicit `vault init --unlock passphrase`): tkinter masked dialog, then KEK = HKDF(scrypt(passphrase) ‖ DPAPI secret). The provider is AAD-bound, and there is no fallback between the two. Hello is unit-tested with a fake signer; on the real machine only `is_supported_async()` has run.
6. **Confirmation:** a `Confirmer` protocol, implemented by `DialogConfirmer`: the shared `signal_confirm` dialog (`packages/confirm`), which shows the name (control and separator characters turned into single spaces) and the live origin. Deny is the default, Allow is mouse-only and armed after 1.5 s, and it denies after 60 s.
7. **TOTP:** not implemented. `CredentialInfo` carries a username hint only.
8. **CLI:** `vault init|add|list|remove`. `init`, `add` and `remove` refuse non-TTY stdin before reading anything. On Windows they also require `GetConsoleMode` to succeed, because NUL reports `isatty()`. `add` reads both values twice with `getpass` and warns (asking for a typed "yes") on excluded categories. `remove` re-seals the remaining records under a fresh DEK, so a pasted-back old record fails as `tampered`.
9. **Audit:** `%LOCALAPPDATA%\signal-vault\audit.jsonl` holds ts, event, credential id (sanitised), top/frame origin labels and the result. It never holds a secret or a full URL.
10. **Trust:** the README opens with a security-sensitive notice: changes need owner review.

Also added: refusal when `DEBUG`, `DEBUG_FILE` or `PWDEBUG` is non-empty (Playwright's wildcards log fill values), a `tampered` result when the AAD fails after unlock, and a `has_filled_fields` that fails closed on frames it can't inspect.
