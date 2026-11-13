# browser_tool.session

Runs the browser session: it opens Edge through a backend (the dedicated desktop profile, or a docker job), enforces the host policy on its traffic, and tracks the open tabs.

## Public API (`from browser_tool.session import ...`)

- `BrowserSession(settings, policy, backend=None, *, allow_relaunch=True, holds_dialogs=True, cookie_mode=None)`
  - `cookie_mode` (`browser_tool.cookie_store.CookieMode`): `OWN` (the desktop server) restores the saved session cookies at each launch, right after the guards are on and before any tool call navigates, and saves every cookie in `close()` before the context closes; `BORROW` (visit mode) restores every unexpired saved cookie its policy allows and never saves; None (docker jobs, tests) leaves `[browser] cookie_file` alone. Neither step can fail a launch or a close.
  - `backend` (`browser_tool.backends`) is where Edge runs: the desktop profile (`LocalBackend`, the default) or a docker job.
  - `start()` launches lazily and is idempotent. It relaunches after the owner closes the window, unless `allow_relaunch=False` (visit mode): then any `start()` after a context closed (window, crash, dropped connection or `close()`) raises `BrowserClosedError`, an `ActionError`, so the tool runner turns it into safe text. It registers the sensitive-field selector engine right after `backend.open_context`, because a CDP-connected default context only gets engines registered once Playwright tracks it.
  - `clear_cookies(domain_pattern)` deletes every cookie whose domain matches the regex (launching if needed). A regex, so one pattern covers host-only (`cas.example.edu`) and domain (`.example.edu`) cookies.
  - `close()` closes the context, then calls `backend.close()` (docker: `docker rm -f`, without waiting). The context's own `close` event (window closed, crash, dropped connection) also calls `backend.close()`.
  - `end_stale_job()` runs before every tool call and closes the session when the backend says its job must end (docker: the host has a new IPv4 address).
  - `job_label` (e.g. `"docker job 1a2b3c"`, None locally) and `idle_close_s` come from the backend.
  - `current_page()`, `pages()`, `current_or_none()`
  - `select_page(index)` raises `IndexError` for a bad index.
  - `block_log` (a `BlockLog`) records requests the guard blocked.
  - `duo` (a `browser_tool.duo.DuoWatch`) follows every tab of each context it opens for Duo prompts.
  - `login_loop` (a `LoginLoopGuard`) counts recent `fill_login`s, for the login-loop refusal.
  - `dialogs` (a `DialogWatch`) holds each tab's confirm, prompt or beforeunload until `answer_dialog` answers it; alerts are accepted and noted. With `holds_dialogs=False` (visit mode, no model to answer) every dialog is dismissed, as Playwright does without a listener.
  - `file_choosers` (a `FileChooserWatch`) intercepts every tab's file picker, so none opens natively; `upload_file` claims the next one of its tab (`claim(page)`, `release(page)`), and others are dropped and noted (`take_opened()`).
  - `downloads` (a `browser_tool.downloads.DownloadRecorder`) saves every download of each context it opens, when the backend has a `downloads_incoming` folder (the desktop browser with `[downloads] enabled`).
- `install_request_guard(context, policy, block_log)`
  - `context.route("**/*")` aborts requests to non-allowed hosts and non-network schemes such as `file:`. `data:`, `blob:` and `about:` pass, because they never leave the browser.
  - A `request` listener records blocked redirect hops. The hops themselves are stopped at DNS level by `--host-resolver-rules`, because routing only sees the first URL of a redirect chain.
  - Logs show origins only, never URLs, headers or post data.
- `BrowserClosedError`: see `allow_relaunch` above.
- `DialogWatch` (`dialogs/watch.py`): `pending(page)`, `all_pending()`, `take(page)` and `restore(pending)` around an answer, `take_alerts()` (the first 5 since the last take, and a count of the rest), `note_trigger(page, texts)` (the last action's texts, copied into a dialog it opens), `begin_act` and `end_act` (a dialog opening meanwhile is `during_act`), `subscribe(callback)` and `keep(task)` (holds background work). A `PendingDialog` has the dialog, its tab, kind, message and preset (capped at 500 characters), trigger and `during_act`. Messages are never logged.
- `act_until_dialog`, `read_until_dialog` and `run_unless_dialog` (`dialogs/race.py`): a dialog freezes its tab, and Playwright's click, press, fill and evaluate on it then never return. The first runs an action and returns False when it opens a dialog (the action finishes in the background once answered); the second runs read-only work and cancels it; the third runs a whole tool call and refuses it with `STOPPED_BY_DIALOG` when a dialog that didn't open during an act freezes the current tab.
- `LoginLoopGuard(clock=time.monotonic)` (pure) counts fills per site: `note_fill(site)` after an ok fill, and `is_loop(site)`, True once the site has `MAX_FILLS_PER_WINDOW` (2: a login plus one retry) fills under `LOOP_WINDOW_S` (10 minutes) old, so the next fill is refused. Fills are counted rather than page landings, because federated and SSO logins pass through choosers and hand-off pages. It only ever refuses more; nothing but time clears it.
- `BlockLog.drain() -> list[BlockedRequest(origin, reason, is_navigation, is_redirect)]`
- `clear_debug_env()` removes `DEBUG`, `DEBUG_FILE` and `PWDEBUG` before Playwright starts. With `DEBUG=pw:api`, the driver would log `fill("<value>")` calls.

## Files

- `browser_session.py`: lifecycle and tabs.
- `debug_env.py`: the debug-env scrub, run before Playwright starts for every backend.
- `request_guard.py`: routing, the redirect-hop listener and `BlockLog`.
- `pdf_downloads.py`: `PdfDownloads`, a CDP Fetch session per tab paused at the response stage for document loads; a PDF response goes on with `Content-Disposition: attachment`, so Edge saves it as a download (through `browser_tool.downloads`) and never opens its viewer. A popup's first load can beat the attach (the scrub's frame timeout covers that).
- `login_loop.py`: `LoginLoopGuard`.
- `dialogs/`: `DialogWatch` (`watch.py`), the dialog races (`race.py`) and `FileChooserWatch` (`file_chooser.py`).

## Dependencies

`playwright`, plus `browser_tool.errors` (the `ActionError` base), `browser_tool.backends` (where Edge runs), `browser_tool.config`, `browser_tool.policy`, `browser_tool.redaction` (it registers the sensitive-field selector engine after the context opens), `browser_tool.duo` (the Duo watcher) and `browser_tool.downloads` (saving downloads).
