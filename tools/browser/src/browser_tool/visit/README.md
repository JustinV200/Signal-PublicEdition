# browser_tool.visit

Visit mode: `browser-tool-visit` visits a fixed plan of pages in one local Edge launch and writes their snapshots to a file, with no model in the loop. Checker v2 (`refdocs/research/checker-v2.md`, section 3.1) runs it twice per check, once with `browser-checker-classroom.toml` and once with `browser-checker-moodle.toml` (gitignored copies of the `*.example.toml` files, which setup fills in), both on the checker's own profile `tools/browser/.profile-checker/`, signed in with cookies borrowed from the desktop browser.

## Command

`browser-tool-visit --config <site config> --plan <plan.json> --out <out.json>`

- The config is one site's (`load_settings`). A config with `[policy] allow_all = true`, or one whose profile is the desktop `.profile`, is refused before anything starts.
- The plan is `{"targets": [{"key": ..., "url": ..., "site": ...}]}`: 1 to 12 targets, unique slug keys, one site. Every URL must be a plain https URL allowed by this config's policy, or the whole plan is refused before Edge starts.
- The out file is `{"status": "ok"|"busy"|"error", "pages": [{"key", "status", "url", "text"}]}`, written on every exit the command controls (a kill from outside can't, so a missing file means error). A page's `url` is the target's `display_url` (no query string); `text` is only what `ToolRunner.run` returned, so it's scrubbed and wrapped in `<untrusted_page_content>`. Page statuses: `ok`, `error`, `login_needed`, `google_signin_needed`.
- Exit code 0 when the status is ok, 1 otherwise. Logs go to stderr and never hold page text.

## What a launch does

- `ActionContext.create(settings, DialogConfirmer, LazyVaultFiller(), LocalBackend(settings), allow_relaunch=False, holds_dialogs=False, cookie_mode=CookieMode.BORROW)`: a local, headed Edge (never the docker backend).
- Shared sign-in: at launch, before the first target, the session adds the desktop browser's saved cookies (`[browser] cookie_file`, `browser_tool.cookie_store`) for every host this config's policy allows, unexpired ones only, and never writes the file. Two Edges can't open one profile at once, and running the visit inside the desktop server's Edge would put its cookie clear, its dismissed dialogs and its looser policy next to the interactive tabs, so it borrows cookies in its own process instead. The cookies are as fresh as the desktop server's last clean close; with no file it starts signed out, as before. Once the window closes, crashes or disconnects, every later action fails with `BrowserClosedError`, so a relaunched Edge without the run's login never acts. Page dialogs are dismissed, as before: there is no model to answer them.
- Launch first: `ctx.session.start()` outside the runner. A failure is `busy` if the profile's `lockfile` is there after retrying for up to 10 s (`launch.py`), else `error`.
- A launch with `[visit] signin_hosts` (Classroom) first clears every cookie on `[visit] school_domain` (`BrowserSession.clear_cookies`, pattern in `sso.py`).
- Per target, everything through `ToolRunner.run`: `navigate`, a `networkidle` wait capped at `settle_s`, then:
  - on a `signin_hosts` host, or after a failed navigation whose last main-frame hop (`hops.py`) went to one or to `[visit] sso_host`: `google_signin_needed` for it and every later target;
  - on `[visit] login_host`: one `fill_login(login_credential, submit=True)` per run, only if `login.is_fill_allowed` (the target's host and the login URL's single https `service`, with no userinfo or port, are on `login_from_hosts`). Then the tab is watched with `duo.wait_until_off_duo` (frame events, plus a poll every second) until it leaves the login host and Duo (up to `login_wait_s`) and the target is loaded again. A refused fill is `login_needed` for that target; a failed fill or wait is `login_needed` for it and every later one;
  - otherwise `snapshot`, and the target is `ok`.
- There's no code path to `click`, `type_text`, `press_key`, `select_option` or `screenshot`. Edge closes at the end.

## Public API (`from browser_tool.visit import ...`)

- `parse_plan(data, policy) -> tuple[Target, ...]`, raising `PlanError`. `MAX_TARGETS` is 12.
- `run_visit(ctx, targets, visit_settings) -> VisitResult(status, pages)`, with `PageResult(key, status, url, text)`.
- `write_out(path, result)`.

## Files

`cli.py` (the command), `plan.py`, `launch.py` (launch and busy), `runner.py` (the per-target loop), `login.py` (the fill rule, the fill and the wait), `hops.py` (main-frame hop hosts), `sso.py` (the school SSO patterns from the config), `result.py` (statuses and the out file).

## Dependencies

`browser_tool.actions` (navigate, snapshot, fill_login), `browser_tool.server.tool_runner` (`ToolRunner`), `browser_tool.backends` (`LocalBackend`), `browser_tool.config` (`[visit]` is `VisitSettings`), `browser_tool.credentials` (the lazy vault), `browser_tool.gates`, `browser_tool.policy`, `browser_tool.duo` (`is_duo_url`), `browser_tool.cookie_store` (`CookieMode`) and `playwright`.
