# tools/browser

A thin Python MCP server that lets Claude Code (and later the audiohub voice assistant) drive a dedicated Microsoft Edge profile through Playwright, with safety controls enforced in code. The design follows `refdocs/research/browser-control.md`. The vault contract is in `refdocs/research/password-vault.md`.

## Run

- The server is a uv project. It needs Python 3.12 and the installed Edge. There is no `playwright install`, because `channel="msedge"` uses the installed Edge.
- Run it with `uv run --project tools/browser browser-tool`. It speaks MCP over stdio and logs to stderr.
- The browser launches on the first tool call, headed, using the profile at `tools/browser/.profile/`.
  - Log in to sites by hand in that window once. The profile keeps the sign-ins through persistent cookies.
  - Session cookies (a site's "log out when the browser closes" kind) survive restarts through the saved-cookies file. On a clean close (the server exiting) the browser saves its cookies to `tools/browser/.state/cookies.bin` (`[browser] cookie_file`, gitignored), encrypted with DPAPI for the owner's Windows login and readable by the owner's account only. At the next launch, before any page loads, its unexpired session cookies for allowed hosts come back. The file is never logged or shown to the model, and `upload_file` and `read_download` refuse anything in `.state`. A missing, corrupt or undecryptable file is ignored with a log line naming the error type only. Code: `src/browser_tool/cookie_store/`.
  - A killed server, or a window closed by hand, saves nothing, so the next launch gets the session cookies of the last clean close. Sites still expire sessions themselves; nothing keeps them alive.
  - Only one browser can use the profile at a time.
- `browser-tool --check` is the setup tool's health check: it loads the config and parses its host patterns as a start would, prints one JSON line (`config OK, N sites allowed`, or the config problem that would stop the server) and exits, without opening a browser.
- Copy `browser.example.toml` to `browser.toml` and list the sites under `[policy] allow`. The default allowlist is empty, which blocks every site. The example file has a commented sample list, and documents every key and its default.

### The docker browser (`browser-docker`)

`browser-tool --backend docker --config tools/browser/browser-docker.toml` is a second MCP server, `browser-docker`, beside the unchanged desktop one. Each job runs Edge for Linux in a throwaway container, so it leaves the owner's screen and desktop browser alone. The desktop browser stays the default; the model uses `browser-docker` when the owner asks for a container job. The design is `refdocs/research/docker-browser.md`, and the code is in `src/browser_tool/backends/` and `docker/`.

- One-time setup: build the image with `docker build --pull --no-cache -t signal-browser:latest tools/browser/docker` (about 300 MB of downloads), and copy `browser.example.toml` to `browser-docker.toml` (gitignored). Its `[policy]` applies to container jobs only, so `allow_all = true` there leaves the desktop allowlist alone.
- Docker Desktop must be running. Nothing touches Docker until the first tool call; if it isn't running, the tool says "Docker Desktop isn't running. Start it and try again."
- A job is one container. It starts on the first tool call and ends when the server exits, after `[browser] idle_close_min` (15) minutes without a tool call, when the PC gets a new IPv4 address, or when its browser dies. The next call starts a fresh one: nothing persists between jobs. If the server is killed outright, the container's relay removes it about a minute later.
- No vault and no logins: the server has no `list_credentials` or `fill_login`, never imports the vault, and its instructions say never to type passwords or codes.
- The backend refuses an image whose Edge is a major version behind Microsoft's Linux stable channel and prints the rebuild command; an older build only warns in the log.
- Owner dialogs and Duo voice notes start with "docker job <id>".

### Visit mode (`browser-tool-visit`)

`browser-tool-visit --config <site config> --plan <json> --out <json>` visits a fixed list of pages in one local Edge launch with no model in the loop, for checker v2 (`refdocs/research/checker-v2.md`). Every action still goes through the tool runner, so the policy, scrubbing and Duo watcher apply unchanged. See `src/browser_tool/visit/README.md`.

- It runs on its own profile, `tools/browser/.profile-checker/` (gitignored), never the desktop `.profile/`: two Edges can't open one profile at once.
- It shares the desktop browser's sign-in by borrowing the saved-cookies file (above) at launch: every unexpired cookie for a host its own stricter allowlist allows, so the Classroom launch gets Google's and the Moodle launch gets Moodle's, CAS's and Duo's. It never writes the file, and it runs in its own process and Edge, so its dismissed dialogs and its policy never touch the desktop's tabs. The cookies are as fresh as the desktop server's last clean close.
- Its two configs are the checker's security policy: `browser-checker-classroom.example.toml` (Google only, no SSO) and `browser-checker-moodle.example.toml` (Moodle, SSO and Duo, no Google). `setup mail-digest` copies them to the gitignored `browser-checker-*.toml` and fills in your school's hosts. `tests/visit/test_checker_configs.py` checks the examples' allowlists by policy match.
- After adding the entry point, `uv sync` (with the MCP servers stopped) installs the `browser-tool-visit` command.

## Tools

`navigate(url)`, `snapshot(ref=None, page=1)`, `find(text, max_results=20)`, `wait_for(text, gone_ref, url_contains, network_idle, timeout_s=10)`, `click(ref, button="left", double=False, modifiers=[])`, `click_at(x, y)`, `drag(source, target)`, `hover(ref)`, `scroll(ref=None, direction="down", amount=1)`, `type_text(ref, text, append=False, slowly=False)`, `select_option(ref, value or [values])`, `press_key(key)`, `back()`, `forward()`, `reload()`, `tabs()`, `switch_tab(index)`, `new_tab(url)`, `close_tab(index)`, `screenshot(ref=None, full_page=False)`, `wait_for_duo(timeout_s=90, wait_anyway=False)`, `answer_dialog(accept, text=None)`, `upload_file(ref, path)`, `read_download(path, pages=None)`, `list_credentials()`, `fill_login(credential_id, submit=False)`. See `src/browser_tool/server/README.md` for what each returns. The docker server has all but the last four.

There is no tool that starts a download: on the desktop browser, a `navigate` to a download URL or a click that starts a download saves the file (see Downloads below), and a tool result reports it. `read_download` then reads a saved PDF's or text file's text.

## Safety controls

The action gates below are best-effort defence in depth. The hard boundaries are the domain allowlist (default: block all) and the vault's per-fill confirmation.

- **Domain allow/deny**, from `[policy]`.
  - Every request goes through `context.route`. Non-allowed hosts and non-network schemes such as `file:` are aborted.
  - Playwright routing never sees redirect hops, so the same policy is also compiled into Edge's `--host-resolver-rules`. Blocked hosts fail DNS before any request is sent, and this was verified on redirects.
  - An empty allowlist blocks everything. `allow_all = true` allows everything except the denylist, and logs navigations.
  - Edge ignores the system proxy (`--no-proxy-server`) unless `use_system_proxy = true`. Behind a proxy, the DNS-level redirect block wouldn't apply.
  - `about:blank`, `about:srcdoc`, `data:` and `blob:` frames count as origin mismatches.
- **Docker jobs only: the host and LAN block**, whatever `[policy]` says, in two layers built from one list (`BLOCKED_GUEST_CIDRS`: 10/8, 172.16/12, 192.168/16, 169.254/16, 100.64/10, 127/8) plus the PC's own IPv4 addresses, read again on every tool call.
  - Layer 1, the policy: routing and `--host-resolver-rules` refuse `docker.internal`, `localhost` and their subdomains, the PC's addresses, and any IP literal that isn't globally routable (IPv4-mapped IPv6 unwrapped).
  - Layer 2, the real boundary: the guest's iptables rejects every packet to those ranges and addresses (DNS to Docker's resolver excepted), and drops all IPv6. The container won't start unless the rules check out.
  - A public LAN (one on public addresses) stays reachable, as from the desktop browser.
  - Docker jobs deny every download over CDP before any page action, and no host folder is mounted. Only the desktop browser saves downloads (below).
- **Downloads (desktop browser only).** `[downloads] enabled` (default on) lets the desktop browser save downloads; the docker browser always refuses them, and the checker configs turn them off. Code: `src/browser_tool/downloads/`.
  - A download is saved only if it comes from a host `[policy]` allows: its URL already went through routing and the DNS block like any request, and it is checked again (Playwright's download URL is the final one, after redirects; verified on headless Edge); a `blob:` or `data:` download counts as the page that made it.
  - Edge writes it to a folder inside the profile first. Past `[downloads] max_mb` (200) it is cancelled and its partial file deleted; a finished file over the cap is deleted too. One with no progress for 60 s, or still running after 30 minutes, is cancelled too.
  - It is then copied to `[downloads] folder` (`tools/browser/.downloads/`, gitignored) under a safe name: no folders, no `.` or `..`, no Windows forbidden characters or device names (`CON`, `nul.txt`, `COM1`...), no control or format characters (bidi overrides and zero-width characters, which can disguise `.exe` as `.pdf`), `.download` added to shell-handled types Explorer acts on just by showing them (`.url`, `.scf`, `.lnk`, `.library-ms`, `.searchconnector-ms`), at most 120 characters, and ` (1)`, ` (2)`... on a clash, so nothing is overwritten.
  - It is never opened, run or unpacked.
  - Every tool result, success or error, reports the downloads that finished: the path, the size and the original name (in `<untrusted_page_content>`, since the name is page data), or why one wasn't saved. A call waits up to 60 s for the downloads it started itself; older running ones are reported by a later call, so one slow download can't hold up every call. `navigate` to a download URL returns "started a download" instead of failing.
  - A PDF is always saved as a download, never shown in Edge's PDF viewer (which tools can't read): every tab's document responses are checked over CDP, and one whose Content-Type is a PDF gets `Content-Disposition: attachment` (`session/pdf_downloads.py`; Edge ignores the `plugins.always_open_pdf_externally` pref under Playwright). It then goes through the checks above.
  - `read_download(path, pages)` reads a saved file's text: only inside `[downloads] folder`, with the same path rules as uploads (below; judged lexically before any disk access), only `.pdf`, `.txt`, `.csv`, `.md`, `.json` and `.log`, at most 50 MB. PDF text comes from pypdf in a child process, at most 20 pages per call and 20 s (it is killed past that); its errors are never echoed. The whole text is scrubbed of secrets, then cut at `[browser] max_snapshot_chars`, then wrapped as untrusted. Docker has no `read_download`.
  - No owner dialog: a download sends nothing out and stays in that folder, so it is treated like navigating to an allowed page, which doesn't ask either. A click that starts one still goes through the click gates. Logs show the source origin and size, never the file name.
- **Redaction.**
  - Playwright 1.64 prints password values in aria snapshots, so every snapshot is post-processed. Password, OTP and similar field values become `"[redacted]"`.
  - Screenshots mask those fields.
  - Long snapshots come in pages of `[browser] max_snapshot_chars` (40k). `snapshot(page=N)`, `snapshot(ref=...)` and `find` read only the tab's cached snapshot, which holds the already-redacted text and is dropped when the tab navigates or a new snapshot is taken; `wait_for` answers only met or not met. `find` and `wait_for` refuse a Duo tab first.
  - `snapshot`, `find`, `wait_for` and `screenshot` refuse while the vault reports filled fields.
  - Every result, including errors, labels and tab titles, has the live value of every secret field replaced. This catches values that leak through `aria-labelledby` names or labels. The result then passes through the vault's `scrub()`.
  - Page content is wrapped in `<untrusted_page_content>`. That includes snapshots, tab titles and the element labels in action results.
- **`type_text` refuses** password and OTP fields, and tells the model to use `fill_login`. `[gates] allow_secret_fields = true` lifts that for `type_text` only, for the job runner's dedicated job-site accounts (`browser-jobs.toml`); it is off by default and stays off in `browser.toml`. Typed values are still never logged, and snapshots and results still redact and scrub them. In those fields, `press_key` allows only navigation keys. `type_text` never presses Enter or Tab, even with `slowly`: line breaks go in through the DOM, since Edge submits a single-field form even on an inserted line break.
- **Every pointer path is gated.** A double, right, middle or modified `click`, `click_at` (on the deepest element at the point, through iframes) and `drag` (the stricter of its two ends) all reach the purchase, send and delete rules. `hover` and `scroll` never ask but still run the Duo, origin and frame checks. `select_option` with several values is gated on every option.
- **Page dialogs.** An alert is accepted at once and reported. A confirm, prompt or beforeunload freezes its tab until `answer_dialog` answers it: every result shows it (its message in `<untrusted_page_content>`), and every action and read tool refuses that tab meanwhile. Accepting is gated on the message plus the label of the action that opened it, so an accepted "Delete 3 messages?", or "Are you sure?" after clicking "Delete", asks as a delete. Dismissing never asks. A prompt asking for a password, passcode, PIN or code gets no text. A tool stuck on a dialog it didn't act for (a confirm opened by a hover) is stopped instead of hanging. Code: `src/browser_tool/session/dialogs/`, `src/browser_tool/actions/dialogs/`.
- **Uploads (desktop browser only).** No native file picker ever opens: every tab's picker is intercepted, and one the page opened by itself is dropped and noted. `upload_file(ref, path)` always runs the send rule, and the owner dialog names the file and its size. Before any filesystem call the path must be a plain drive-letter path inside a root (no UNC share, which would leak an NTLM handshake, no `\\?\` or `\\.\` prefix, no device name such as `CON` or `nul.txt`). Every part of the path is then lstat-checked from the drive root down, so a symlink or junction (even one to a network share) is refused before anything follows it, and the file must resolve, with no short name on the way, to a regular single-name file inside `[uploads] roots` (`life/` and `.downloads/`), at most `[uploads] max_mb` (25). The vault's folder, `.profile*`, `.state` (the saved cookies), `.env*`, `*.env` and key files are always refused. A root or the downloads folder on a network share or mapped network drive is a config error. The file is opened once and its bytes are uploaded, never the path. The docker browser has no `upload_file`. Code: `src/browser_tool/actions/uploads/`.
- **Form resubmission.** Edge silently re-sends a form's POST when a tab reloads, or goes back or forward onto, a page a form submitted to. `reload`, `back` and `forward` hold that back and ask as a send (or log, when send isn't in `always_confirm`). `new_tab` goes through navigate's policy check before it opens a tab.
- **Owner confirmation.** Auto-allow is the default. Navigation, ordinary clicks, typing, dropdown choices and key presses run without a dialog. Only actions in a `[gates] always_confirm` category wait for an Allow in the topmost owner dialog (`signal_confirm`, `packages/confirm`). The default list has all three:
  - `purchase`: buy, purchase, pay, checkout, place or confirm an order, subscribe, donate, transfer, withdraw.
  - `send`: send, post, reply, comment, publish, submit, unsubmit, turn in, hand in, mark as done (Google Classroom hands work in on it), share, upload, and request access (Drive emails the owner), unsubscribe, and GitHub's merge, commit and close issue, pull request or "close as" (broad on purpose). Also:
    - a submit control in a form that isn't a search form (inside `<search>` or `role=search`, or with one search field as its only text field) or an explicit `method="get"` form (Moodle's "Add submission"), unless it is a sign-in submit (below), and Enter that submits one, from any field, checkbox or radio, including Enter in a form's only text input when it has no submit button. Only "Save draft" and "Save as draft" are exempt; "Save changes" asks, because Moodle with drafts off hands the work in on it. The word rules still apply in GET forms.
    - Control+Enter or Meta+Enter, wherever focus is, unless it is in a search box or search form.
    - Enter in a textarea or contenteditable message box, except on `[gates] no_confirm_origins`. A `role=combobox` box (an @-mention composer is one) is a message box unless it is in a search landmark or is an `<input>` that is a search form's only field.
  - `delete`: delete, remove, trash, and the Delete key.
  - Signing in and OAuth consent don't ask: approval is only for purchases, sends and deletes. A submit doesn't count as a send when it is a sign-in submit: its own form (including via `form=`) has a visible password field that is filled (only its length is read; a decoy is never filled, and `fill_login` fills the real one with the vault's approval), no textarea, contenteditable, file field or custom element (which may hide an editor in its shadow DOM), and at most two other rendered text fields; and its whole label is sign-in wording (log in, login, sign in, signin, sign on, log on, next, continue or verify, any case, with optional trailing arrows or punctuation; `config.SIGN_IN_WORDING_RE`). For Enter, the label is that of the form's default submit button, and an implicit submission with no button has none. Visible means rendered, bigger than 1x1 px, on the page, drawn at 0.1 opacity or more, not cut away by a clip-path, clip or a 1px overflow-hidden ancestor, and not covered (a hit test at its centre finds it). Anything else, such as an empty password field, "Save changes", "Post", "Update", "Go" or "Submit", keeps the send rule, and hidden password decoys and whole-page forms still ask. The word rules still apply to its buttons. Passwords still go only through the vault, which asks before every `fill_login`. Older configs that list `password_submit` or `grant_access` still load; each retired name is ignored with a warning.
  - The words are whole-word, case-insensitive regexes (`browser_tool.config.CATEGORY_PATTERNS`). `[gates] patterns` adds the owner's own, which always ask.
  - Click rules run on the element actually hit at the click point, on every ancestor across shadow hosts, and on a clicked `<label>`'s control, because clicks bubble. Key rules run on the focused element and its form's submit controls. Dropdown choices match on the live select name and option label or value.
  - Whatever used to ask but isn't on the list runs and gets one INFO log line with the tool, the ref and role or the key name, the origin and the reason, never page text or typed text. That covers actions inside opaque-origin frames, clicks that land in an `<iframe>`, other key presses, and categories left off the list.
  - The list comes only from `browser.toml`. No tool and no page can change it. An empty list asks for nothing, and the vault's per-fill confirmation and the Duo lockout stay on either way.
  - In password and OTP fields, `press_key` still refuses everything but Tab, Shift+Tab and Escape. Control characters and unknown key names are rejected. The arrows, Home, End, PageUp and PageDown reach the rules only when focus is on a form control, an ARIA widget or a closed shadow host, where they change values.
  - Deny is the default and Allow has no keyboard shortcut, so a stray keystroke can't approve. A timeout, or a dialog that fails to show, counts as no.
  - The owner can take up to `[gates] confirm_timeout_s` (120 s) to answer, and the tab can move meanwhile. Right before every click, drag, hover, scroll, fill, select and key press, asked or not, the page is checked against the policy and for Duo again, and an approved action must still be on the origin the dialog showed. Otherwise it is refused. `press_key` has no element to pin it to a page, so this is what stops an approved Delete from landing on another site.
  - No MCP tool can answer the dialog. Known limit: the model's shell runs as the same Windows user, so a same-user process could in principle script it. This is the same-user limit described in `refdocs/research/password-vault.md`.
- **No leaks through errors or logs.**
  - Raw Playwright exception text is never returned or logged, because call logs can contain `fill("<value>")`.
  - `DEBUG`, `DEBUG_FILE` and `PWDEBUG` are cleared before Playwright starts.
  - There is no HAR, trace or video recording.
  - Logs show origins, refs, roles and key names, never page text or typed text.
- **Edge sandbox.** Edge launches with `chromium_sandbox=True`, which stops Playwright adding `--no-sandbox`, so it keeps its Chromium sandbox. Verified via `edge://sandbox`.
- **No browser password saving.** The profile's Edge prefs turn off the password manager and autofill. Verified via `edge://prefs-internals`.
- **Signed out and login loops.** When `navigate`, `back`, `forward`, `reload`, `new_tab`, `click`, `click_at`, `drag`, `press_key` or `wait_for_duo` leaves the tab on a page whose main frame shows a visible password field (after letting the landing settle when the action navigated the main frame, or for up to 10 s after Duo), the result says so and suggests one `fill_login`. Account choosers and SSO hand-off pages without a password field get no note. A wrong-password retry is allowed once: a third `fill_login` on the same site within 10 minutes is refused ("login loop ... asked to sign in again right after a login. Stop and tell the owner"), which also stops repeated wrong passwords from locking the account. The guard only refuses; passwords still go only through the vault.
- **Duo.** Duo two-factor prompts are owner-only: the owner approves on their phone, never Claude. Details are in `src/browser_tool/duo/README.md`.
  - A tab is in a Duo prompt while its page or any iframe is on `duosecurity.com` or a subdomain, by parsed hostname. Lookalikes don't count; a host that can't be read does. A popup that a Duo tab opens counts too, while it is on a page with no host.
  - While the current tab is in one, `click`, `click_at`, `drag`, `hover`, `scroll`, `type_text`, `select_option`, `press_key`, `reload`, `fill_login`, `find`, `wait_for` and `screenshot` refuse. `navigate`, `back`, `forward`, `switch_tab`, `new_tab`, `close_tab`, `snapshot`, `tabs` and `wait_for_duo` still work.
  - `wait_for_duo()` waits, read only, for the owner's approval (up to `timeout_s`, at most 300 s), then reports where the tab landed. It never acts in Duo. The voice ping rings through sleep and away, but the owner may not answer, so a timeout is a normal, clean result. If a hub that doesn't honour ring-through dropped the ping, it says so at once instead of waiting, unless `wait_anyway=true`.
  - The pointer tools, `type_text`, `select_option` and `press_key` check again right before they touch the page, because an owner dialog can wait long enough for the tab to redirect to Duo. `fill_login` checks only when it is called (see Known gaps).
  - Once per prompt, the next tool result ends with a notice naming the tab, telling Claude to wait and, if it can, to send the owner a phone push. Only the latest notice per tab waits, so a page that keeps re-adding a Duo frame can't pile them up.
  - The notice and the voice note name the site by hostname only, and only if it is plain `[a-z0-9.-]`. Anything else reads "a login". A host in `[duo] site_names` (exact hostname to a plain name, e.g. `"sso.example.edu" = "the school login"`) is said by that name instead.
  - The notice ends with one line on the voice ping: `voice ping: spoken`, `voice ping dropped: the owner is asleep` (or away; only from a hub without ring-through), `voice hub not running`, or `voice ping skipped: one was sent under 60 s ago`.
  - Once per prompt, the voice hub also hears an urgent "Duo push for <site>, approve on your phone." It and the code note are marked `ring_through` (the owner's choice, 2026-10-26), so audiohub speaks them even while the owner is asleep or away. It is sent in the background, and skipped with a log line if the hub isn't running. Voice notes are at least `min_heads_up_interval_s` (60 s) apart across all tabs, so a page that keeps embedding a Duo frame can't keep telling the owner to approve.
  - Verified Push codes (read only, off by default): for sites in `[duo] code_relay_sites`, the tool reads the 3 to 6 digit code the Duo frame shows, and once per prompt says "Duo code for <site>: 4 8 2. Type it in Duo Mobile and approve." and gives Claude an updated notice with the code for its phone push. It reads only a top-level Duo page (the Universal Prompt) and Duo frames nested purely in it, never a Duo frame a page embeds, and relays nothing unless exactly one code is found. The prompt's site is the page before Duo, and is forgotten if the navigation to Duo passed through another host, came from a page with no host, wasn't started by the site's own page (its first request must carry a `Referer` on the site; a missing one fails closed), or arrived through back/forward history. At most one code per site is relayed per `min_heads_up_interval_s`, voice and notice alike. Prefer exact login hosts: a wildcard like `*.example.edu` trusts every subdomain. The list is empty by default because someone with the owner's password could embed a real Duo prompt on their own page, and hearing its code would prime the owner to approve them. The code note skips `min_heads_up_interval_s`, since its prompt's heads-up was already sent or rate-limited. Clicking and typing in Duo stay locked.
  - `[duo]` in `browser.toml` controls the voice heads-up, the hub's address, when a return to Duo is a new prompt, and the code relay. The lockout and the notice are always on.
  - Duo logins load only if the policy allows Duo: `*.duosecurity.com` in `[policy] allow`, or `allow_all = true`.

## Vault

The `LoginFiller` protocol is in `browser_tool.credentials`. The vault package (`tools/vault`) is loaded lazily once it is a path dependency (`uv add --editable ../vault`). Until then, the credential tools return `vault not installed`.

## Layout

```
src/browser_tool/
  config/       settings dataclasses, TOML loader, paths
  policy/       allow/deny decisions, host-resolver rules (pure Python)
  redaction/    sensitive-field selector engine, snapshot redaction
  gates/        Confirmer protocol, owner dialog adapter, action rules
  credentials/  LoginFiller protocol, vault loader, result formatting
  backends/     where Edge runs: the desktop profile, or one container per docker job
  downloads/    saving the desktop browser's downloads: safe names, the size cap, the policy check
  cookie_store/ the DPAPI-encrypted saved cookies: saved on a clean close, restored at launch
  session/      lifecycle through a backend, request guard, tabs, held page dialogs
  duo/          Duo prompt detection, the voice heads-up, the code relay, the lockout check
  actions/      one function per MCP tool
  server/       MCPServer, tool definitions, tool runner, entry point
  visit/        visit mode (browser-tool-visit): fixed pages, no model
  errors.py     the ActionError base, below every subpackage
tests/          mirrors src/; Edge runs headless against local http.server fixtures
docker/         the docker jobs' guest image (Dockerfile, guest code, seccomp profile), phase 0 probes
```

## Tests

`uv run --project tools/browser pytest` runs the suite. The browser tests launch headless Edge against a local `http.server`, using `*.localhost` host names, which Chromium resolves to loopback.

Tests marked `docker` drive a real container and need Docker Desktop, the built image and the internet. They are skipped by default; run them with `pytest -m docker`.

## Dependencies

- `playwright==1.64.0` drives Edge.
- `mcp==2.3.0` is the MCP server SDK, the same pin as audiohub.
- `signal-hub-notify` (`packages/hubnotify`, stdlib only) delivers the Duo heads-up to the voice hub.
- Dev only: `pytest`, `pytest-asyncio`, `ruff`.

## Known gaps

- A popup's very first load can start before its PDF rule attaches, so a PDF opened straight into a new tab may still show the viewer. Every tool then fails closed (the result is withheld because secret scrubbing failed, naming the tab and suggesting `close_tab(N)`) instead of hanging, since the scrub gives each frame 2 s; close that tab to carry on. A PDF in an `<embed>` or `<object>` isn't a document load and isn't caught either.
- A PDF in a cross-origin iframe that Edge runs out of process may not be caught by the PDF rule (that iframe has its own CDP target), so the viewer can load there. Results are then withheld the same way until that tab is closed.
- A `blob:` PDF in an iframe (a page that builds the PDF in script) never reaches the network, so the PDF rule can't see it and Edge's viewer loads. Results are then withheld the same way until that tab is closed.

- `click` and `click_at` hover first, let hover effects settle for 300 ms, judge the element, and judge it again right before the click (refusing one that now asks more than was approved). A page that changes the element on pointerdown, or in the last tens of ms before the click, isn't caught. Neither is a page that sends from an innocent-looking button's onclick: the rules only see names and text.
- `type_text(slowly=true)` checks focus before every key, but a page that moves focus on keydown gets that one key in the new place (a space can press a button) before the next check stops the typing.
- A password re-prompt (a form with just a password field) whose button says "Continue" or "Verify" counts as a sign-in submit, so it skips the send rule even if the re-prompt confirms a send. The vault still asks before filling that password, which is the owner's chance to stop it.
- A settings wizard whose page fills its own password field (a router or NAS setup) and whose button says "Next" or "Continue" counts as a sign-in submit, so it skips the send rule.
- A tab frozen by a dialog can't be read, so the result scrub uses its secret values as last read (every result refreshes them). A value typed into that tab after the last tool result and before the dialog opened isn't known to the scrub.
- A tab gets its file-picker intercept a moment after it opens, so a page that opens a picker in that instant would show the native one.
- Uploads from the docker browser wait on the owner's decision (D8); its server has no `upload_file`.
- `upload_file` resolves the path again after opening the file and refuses a change, but a folder swapped for a junction and back in between the checks and the open isn't caught. The opened file must still be the one the checks saw, and inside the roots by name.
- A click's download can start a moment after the click returns. It is then reported with the next tool result, not the click's.
- The size cap can't tell which in-flight file belongs to which download, so a file past the cap cancels every download still running, and any file growing counts as progress for each. Fine while downloads come one at a time. A cancel for stalling leaves the partial file to Edge, and the next launch clears any leftover.
- With `use_system_proxy = true`, DNS-level redirect blocking doesn't apply. The landing-page backstop still clears the tab.
- A deny entry inside an allowed wildcard is not DNS-blocked for redirect hops, because Chromium's EXCLUDE rule wins. Routing still blocks direct requests to it.
- WebSockets aren't routed. They are only DNS-blocked, and only when the policy has rules.
- Page scripts can copy a secret into ordinary text. The vault's `scrub()` is the defence there.
- Gating is by element text. A page can mislabel a purchase button.
- Enter that sends from a plain `<input>` outside a form (some chat apps) isn't `send`: only a textarea or contenteditable counts as a message box. Neither are keyboard shortcuts that act without a focused button, such as a mail app's `#` for delete.
- Calendar RSVP buttons (Yes/No/Maybe in Gmail) email the organizer but have no stable word, so they run unprompted.
- A frame whose whole body is the editor (TinyMCE and other `designMode` editors) isn't seen as focused, so Enter there is only logged.
- An icon button with no accessible name (no text, `aria-label`, `title` or `alt`) is an ordinary click, even when it sends, if it is outside a form or is a `type=button` inside one.
- Some outward actions use words the built-in patterns don't cover, such as GitHub's "Create" outside a form. Granting an app access (an OAuth "Allow", or "Install" for a GitHub app, which grants it repository access) runs without asking. Add the ones you care about to `[gates] patterns`.
- The last-moment re-check (Duo, policy, approved origin) reads the URL the tool last heard about. A navigation the browser has committed but whose event hasn't reached the tool yet isn't seen, and Playwright's own short wait for the element to be ready comes after the check.
- `fill_login` checks for Duo and the policy only when it is called, not after the vault's own Allow dialog. Right before it fills, the vault re-checks the page's and the fields' origins against the credential's registered origins, through the element handles it found first, so a tab that moved meanwhile (to Duo or anywhere else) isn't filled. TODO: a Duo iframe added to the same page meanwhile doesn't stop the fill, though the fill and its optional Enter only touch the site's own login fields. A browser-side re-check there needs a hook inside the vault, such as a pre-fill callback (see `actions/login.py`).
- Saved cookies are live sign-ins: anyone who gets the `.state/cookies.bin` file and can decrypt it has those sessions (session cookies included) until the sites expire them. DPAPI ties it to the owner's Windows login, so a copied file is useless on another account or PC, but any program running as the owner can decrypt it. The visit checker borrows them, so a site may see one sign-in used from two Edge profiles; one that binds sessions to a device could sign one of them out.
- Duo lockout gaps (TODO, see `src/browser_tool/duo/README.md`):
  - A Duo iframe isn't locked until its Duo URL commits, so there is a short window while it loads.
  - The lockout covers the current tab only. A Duo popup doesn't lock the tab that opened it; switching to the popup does.
- A client-side open redirect on a `[duo] code_relay_sites` site itself (JavaScript or `<meta>` sending the tab to a Duo URL from the query or fragment) carries the site's own `Referer`, so its Duo prompt is named after that site and has its code relayed (at most once per site per `min_heads_up_interval_s`). Anything else that sends such a tab to Duo (its opener, a popup it opened, a third-party frame, Claude's `navigate`) is caught by the `Referer` rule. See `src/browser_tool/duo/README.md`, which also lists where that rule fails closed.
