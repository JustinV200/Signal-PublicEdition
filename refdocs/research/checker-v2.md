# Assignment checker v2: on-demand course-site checks

Design, 2026-10-20. Builds on the mail digest (v1, `tools/mail-digest`, routine `refdocs/routines/mail-digest.md`) and the browser tool (`tools/browser`). No site was visited for this doc. **[unverified]** marks site details that phase 0 checks with the owner present.

## 1. Scope

**Goal.** When the owner asks, read the owner's course sites and bring `life/` up to date: each assignment's name, due date, status and link. Then refresh the whiteboard TODO view and send the self-only digest email. That step already exists: `mail_digest/digest_email/step.py` (`email_digest`), which sends through `mail send-self` in `tools/mail`.

**Sites** (course ids from the `life/` course READMEs):

- Moodle (`lms.example.edu`): a few courses, each by its Moodle course id.
- Google Classroom at `/u/N/`, the school account: one or more classes, each by its class id.

**Non-goals:**

- No scheduled runs. 07:00 stays mail-only ("Scheduled runs never trigger Duo" in the digest README).
- Read only. Nothing on a site is clicked, typed, submitted or downloaded.
- No forums, announcements, assignment descriptions, files or grades (decided). Announcements already arrive by email.
- Google sign-in is never automated; the owner signs in themselves in a normal browser window, and the checker reuses that profile's session. No Duo automation.
- No Docker browser. Docker jobs have no logins (`docker-browser.md`).
- No links in `life/`, because the guard's line rules forbid URLs. Links go to `.state/` and the CLI output (section 3.3).

## 2. Launching

- **One CLI**, `assignment-check`, a second entry point in the mail-digest project:
  - `--now` starts a detached run and returns at once, like `mail-digest --now` (`background.start_background_run`).
  - With no flag it runs in the foreground and prints the items with their links.
  - `--dry-run` prints the plan and both argvs.
- **Voice.** "Check my assignments" makes the voice brain run `assignment-check --now` through Bash.
  - Bash is never silent in the voice gate (`SHELL_TOOLS` in `audiohub/brain/permissions/secret_paths.py`, applied in `gate.py`), so the hub first asks "May I run ...?". Keep that question: it doubles as "a Duo push is coming".
  - Add one line to `VOICE_SYSTEM_APPEND` (`brain/voice_prompt.py`) saying to run this command for assignment checks. Today that prompt invites voice to browse Moodle and Classroom itself, with the full browser tool set.
- **Console.** the owner types the request and the console forwards it to the orchestrator, which runs the CLI. No console code. Add a button later only if the owner wants one.
- **`life/README.md`** gets a line like the mail digest's, so sessions know the command and that only the owner starts it.

Why only this: one entry point, reached three ways that already exist, with no new MCP tool and no permission change.

**Who starts it.** Only the owner. Agents never start it on their own, since it opens vault prompts and can send a Duo push. Even if one did:

- the vault's Allow dialog and Windows Hello need a human;
- CAS asks for Duo only after the password;

so no push goes out without the owner.

## 3. Process and permission model

```
assignment-check runner (mail_digest.assignment_check, trusted, holds .state/run.lock)
 1 visit   browser-tool-visit, twice: Classroom config, then  no model: fixed URLs, snapshots,
           Moodle config (separate allowlists, one Edge each)  vault fill on CAS only -> pages.json
 2 reader  claude -p per site, --tools "", no MCP, empty cwd  page text in -> findings out
 3 check   runner validates findings against pages.json       pure Python
 4 writer  claude -p, Read + Edit(exact files), no MCP        validated fields in -> life/ edits
 5 after   v1 guard, announce, whiteboard todo sync, self-only digest email
```

| Step | Sees page text | Tools | Writes |
|---|---|---|---|
| visit | yes, to capture it | browser_tool actions, and a vault fill on the login host | `.state/assignment-check/pages.json` |
| reader | yes | none (only `StructuredOutput`) | nothing |
| check | yes, to validate | none | log, state |
| writer | only validated fields | `Read`, and `Edit` on the run's exact files | inbox, week plan, course READMEs |

**Why no model holds a browser tool.** This is stricter than the navigate, snapshot, tabs and back set in the brief:

- Navigation is the exfiltration channel. A GET to an allowlisted host (a Google Forms `formResponse` URL, or a Moodle link that carries `sesskey`) can leak data or change state.
- CAS and Moodle sign-ins are session cookies, so login and reading must share one Edge process. A `claude -p` spawns its own MCP servers and can't share a trusted login session.
- The pages are fixed index pages (section 4), so a model doesn't need to steer.

The visit step calls only `navigate`, `snapshot` and `fill_login` (in the Moodle launch only), each through `ToolRunner.run`. It has no code path to `click`, `type_text`, `press_key`, `select_option` or `screenshot`. The cost: if a URL or layout changes, `courses.py` needs editing, where a model could have adapted.

### 3.1 Visit mode (`tools/browser`)

- **Command:** `browser-tool-visit --config <site config> --plan <json> --out <json>`. It's a separate `[project.scripts]` entry (`browser_tool.visit.cli:main`) in a new `browser_tool/visit/` package (`cli.py`, `plan.py`, `login.py`, `runner.py`). `server/main.py` stays the MCP entry point only.
- **Two launches per run.** The checker runs `browser-tool-visit` twice, one after the other, under its one run lock and on the checker's own profile (below): first the Classroom launch, then the Moodle launch. Each launch has its own config and only its own site's targets.
  - **Classroom launch** (`browser-checker-classroom.toml`). It allows no `sso.example.edu`, so Google's SAML hop for the school account can never reach CAS, whatever cookies the profile holds.
  - **Moodle launch** (`browser-checker-moodle.toml`). It allows no Google host at all. The DNS resolver rules then block every Google request, redirect hops and Edge's own background requests included.
  - So no single checker Edge ever has both CAS and a Google sign-in host reachable. That's what keeps a checker launch from signing in to Google.
  - **Its own profile.** Both checker configs set `[browser] profile_dir = ".profile-checker"`. That's the existing key (`config/settings.py`, default `.profile`), which `LocalBackend` resolves with `resolve_tool_path` and launches from, so no new hook is needed. `tools/browser/.profile-checker/` is gitignored next to `.profile/` (phase 0).
    - The desktop MCP server keeps `.profile/`, with `allow_all = true`.
    - Nothing a checker run leaves behind (a CAS session after a crash, a kill or a window the owner closed) can reach that browser.
    - Every launch on `.profile-checker/` is a checker launch, under one of the two allowlists.
  - **One belt-and-braces clear.** At the start of the Classroom launch, before any navigation, visit clears every school cookie, so a CAS session left by a crashed earlier run can't meet a Google SAML hop.
    - The hook is a new public `BrowserSession.clear_cookies(domain_pattern)`, which calls `context.clear_cookies(domain=re.compile(r"(^|\.)example\.edu$"))`. Playwright 1.64 accepts a regex for `domain`. An exact string would miss `.sso.example.edu` and `.example.edu` cookies.
    - Nothing else is cleared. The Moodle launch has no Google host to reach.
    - **Duo trust cookie.** Phase 0 checks whether any recorded school cookie is Duo's "trust this browser" cookie. Duo's own cookies are normally on `duosecurity.com`, which the pattern doesn't touch, but this is **[unverified]**. If one is on `example.edu`, the pattern is narrowed to the CAS session cookies by name, or a Duo prompt on every run is accepted (the owner's call then).
  - **What's guaranteed:**
    - no checker launch signs in to Google, because no checker Edge can reach both CAS and a Google sign-in host;
    - the desktop browser never sees the checker's cookies, because it uses a different folder.

    Plain Edge on either profile is out of scope: the owner's own logins in `.profile/`, and anything the owner does by hand in `.profile-checker/` besides the one-time Google sign-in.
- **Per-launch config hook.** It already exists: `load_settings(path)` reads one TOML into a `Settings`, and `ActionContext.create(settings, confirmer, filler, backend=LocalBackend(settings))` builds the `HostPolicy` and the `--host-resolver-rules` from that `Settings`. One config per launch is therefore enough, with no new policy plumbing.
- **Backend.** tools/browser is mid-refactor: `backends/` is new (`LocalBackend`, `DockerBackend`), `session/launcher.py` is gone, and the docker backend is still landing. Visit mode builds on that work and always uses `LocalBackend(settings)`, a local, headed Edge on `.profile-checker/`. It never uses the docker backend, which has no vault.
- **Every action goes through `ToolRunner.run`** (`server/tool_runner.py`), never a bare `actions.*` call. The runner is what:
  - serializes actions;
  - maps Playwright errors to safe text (raw error text can hold `fill("<value>")`);
  - runs `scrub_live_values` and the vault's `scrub()`, and withholds the text if either fails;
  - appends the Duo notices.

  Visit calls `runner.run("navigate", actions.navigate, url)`, `runner.run("snapshot", actions.snapshot)` and, in the Moodle launch only, `runner.run("fill_login", actions.fill_login, id, True)`. A `ToolError` becomes that target's `error` status, and its already-scrubbed text is logged. Only text that `run` returned goes into the out file. The policy, redaction, `<untrusted_page_content>` wrapping, the Duo watcher and its hub heads-up all apply unchanged.
- **The plan** has at most 12 targets, each `{key, url, site}`, all for one site, from `courses.py`. Every URL must be https on that launch's allowlist, or the whole plan is refused before Edge starts.
- **Launch first.** Visit calls `ctx.session.start()` itself, outside the runner, before the first target. A launch failure there is `busy` (or `error` if it's not the profile lock). With its own profile, `busy` now only means another checker run, or the owner's plain-Edge sign-in window on `.profile-checker/`, and the run lock already rules out the first. A third case is an `msedge.exe` on `.profile-checker/` still exiting after the Classroom launch. For that, the Moodle launch waits for the profile lock to clear (up to 10 s) before calling it `busy`; phase 0 checks whether that wait is needed. Inside `runner.run("navigate")` the same failure would only show as a generic navigation error.
- **No silent relaunch.** Today `BrowserSession._on_context_closed` drops the context, and the next tool call relaunches Edge.
  - Visit passes a new `allow_relaunch=False` through `ActionContext.create` to `BrowserSession`. With it, `start()` after any context close raises `BrowserClosedError` instead of launching.
  - `BrowserClosedError` subclasses `ActionError`, so `ToolRunner._invoke` maps it to safe text, not `INTERNAL_ERROR`. Visit's own `ctx.session.start()` call maps it the same way, to `error`.
  - So once the window closes, crashes or disconnects (after a fill or not), every remaining target in that launch gets `error`. A relaunched Edge without the CAS session never runs a second fill.
  - The MCP server keeps its default, `True`.
- **Per target,** `navigate`, then wait for `networkidle`, capped at `settle_s` (Classroom renders client-side). Then:
  - **On `[visit] login_host` (CAS), Moodle launch only.** Only the Moodle config sets `[visit]` login keys, so the Classroom launch has no fill path at all. A fill is allowed only when:
    - the target URL's host is in `login_from_hosts` (`lms.example.edu`);
    - the CAS URL's `service` query parameter parses to an https URL on a `login_from_hosts` host. `actions.navigate` returns no Playwright response, so the redirect chain isn't available through `runner.run`. Visit reads the tab's raw `page.url` (the query string included) from `ctx.session.current_page()`; that value never goes into a result.

      If phase 0 shows `service` isn't reliable, the fallback is a main-frame request listener on that page, the way `duo/prompt_state.py` uses `NavigationHop` and `is_straight_from`.

    Then, at most once per run, `fill_login(login_credential, submit=True)`. Poll the tab's host every second until it leaves the login host and Duo, for up to `login_wait_s`, and navigate to the target again. If the fill isn't `ok`, or the wait runs out, this target and every later Moodle target get `login_needed`. There's no second try.
  - **The Classroom launch lands on `accounts.google.com`, or its navigation is blocked on the way to CAS:** `google_signin_needed`. Nothing is filled or typed.
    - A hop blocked by DNS fails as a navigation error. The request guard does record blocked redirect hops (`request_guard._note_redirect_hop`), but `navigate` drains its block log into prose for the model. So visit keeps its own main-frame request listener on the page, which records each hop's host, redirects included, as structured data.
    - A failed navigation whose last main-frame hop was to `accounts.google.com` or to a `sso.example.edu` host is `google_signin_needed`. Any other failure is `error`.
    - After the first `google_signin_needed`, visit skips the remaining Classroom targets (they get the same status) and closes the launch.
  - **Otherwise:** `snapshot`, and the target is `ok`, with its text.
- **Ordering and routes.** With separate allowlists, neither ordering nor routes is a defence any more.
  - The post-fill `context.route` is dropped: the Moodle launch can't resolve Google hosts anyway.
  - Classroom still runs first, but only so that its results are in even if the owner walks away during the Moodle login.
- **Why DNS-level allowlists are the guarantee.**
  - Playwright's route handlers see only the first URL of a redirect chain. The `--host-resolver-rules` that `HostPolicy` compiles stop every hop, which the browser README notes was verified on redirects.
  - Service workers registered by the one-time plain-Edge Google sign-in on `.profile-checker/` are low-risk: `LocalBackend` blocks them (`service_workers: "block"`), and any fetch they made would still meet the same resolver rules.
  - Startup boost preloads only Edge's default user-data folder, not this custom `--user-data-dir`, so no pre-warmed Edge joins a launch. **[unverified]**; phase 0 checks it.
- **Startup prefs aren't touched.** Visit doesn't write `session.restore_on_startup`. That pref is MAC-protected in Secure Preferences, so a `Preferences` write would be ignored or flagged as tampering. A CAS cookie that survives a restart stays in `.profile-checker/`, where the Classroom launch clears it and the Moodle launch can't reach Google with it.
- **Timeout.** The checker kills each launch after `VISIT_TIMEOUT_S = 15 * 60`. The Moodle launch's worst case is the 60 s vault dialog, plus Hello, plus `login_wait_s` (150 s), plus 9 pages x (30 s navigation timeout + 8 s settle), which is about 10 minutes. Classroom's worst case is 3 x 38 s.
- **The output file:** `{"status": "ok"|"busy"|"error", "pages": [{key, status, url (display_url), text}]}`. Visit writes it on every exit it controls. The timeout kill doesn't let it, so the checker treats a missing or unparseable file as `error`.
  - The profile lock is the session start's failure (see "Launch first"). Whether `.profile-checker/lockfile` tells it apart from other launch failures is **[unverified]**.
  - Edge closes at the end of each launch.
- **`[visit]` is a new settings section**: a dataclass in `config/settings.py`, since `config/loader.py` rejects unknown sections. Its keys are `login_host`, `login_from_hosts`, `login_credential`, `signin_hosts`, `login_wait_s` (150) and `settle_s` (8). An empty `login_host` (the default) means no fill.
- **The two configs** are committed in `tools/browser/`, because they hold no secrets and are the checker's security policy. Both pin `allow_all = false`, `deny = []` and `[browser] use_system_proxy = false` (behind a proxy, the DNS-level redirect block wouldn't apply). The desktop `browser.toml` has `allow_all = true`, and the checker must never inherit it.
  - `browser-checker-classroom.toml`:
    - `[policy] allow = ["classroom.google.com", "accounts.google.com", <Classroom static hosts from phase 0>]`;
    - `[visit] signin_hosts = ["accounts.google.com"]`, with no login keys.
  - `browser-checker-moodle.toml`:
    - `[policy] allow = ["lms.example.edu", "sso.example.edu", "*.duosecurity.com", <Moodle static hosts from phase 0, none of them Google>]`;
    - `[visit] login_host = "sso.example.edu"`, `login_from_hosts = ["lms.example.edu"]`, `login_credential = "school"`;
    - `[duo] code_relay_sites = ["sso.example.edu"]` (decided).
  - Both: `[browser] max_snapshot_chars = 25000` and `headless = false`, so the owner can answer Duo's "trust this browser" prompt. The index pages should be far smaller than that cap. Phase 0 records each real page's size and sets the cap from them.
  - **Hard rules:**
    - the checker never allows `*.google.com` or `www.google.com`;
    - CAS appears only in the Moodle config, and Google hosts only in the Classroom config;
    - static hosts that phase 0 finds for Classroom go only into the Classroom config.

    The test checks policy matches, not strings, since a wildcard such as `*.edu` or `*.com` passes a string test but undoes the block. For each committed config it builds the `HostPolicy` (`load_settings` then `HostPolicy.from_strings`), and asserts that `check_host` is denied for a fixed list:
    - Classroom: `sso.example.edu`, a sample `*.example.edu` host, `www.google.com` and `x.google.com`;
    - Moodle: `accounts.google.com` and `www.google.com`.

    It also asserts `allow_all` is false, `deny` is empty, `use_system_proxy` is false and `profile_dir` is `.profile-checker`.
- **README:** `browser_tool/visit/README.md` covers what visit mode does, its API (`browser-tool-visit`, the plan and out formats), and its dependencies (actions, `server/tool_runner`, backends), per codingrules section 3.

### 3.2 Reader

- **argv,** built like v1's `build_command`, as a list with no shell:
  - `claude -p --restricted`;
  - `--permission-mode dontAsk --permission-prompts none`;
  - `--tools ""`;
  - `--strict-mcp-config` (with no `--mcp-config`);
  - `--append-system-prompt-file <reader routine>`;
  - `--json-schema <schema>`, `--model sonnet`, `--max-budget-usd 1.00`;
  - `--disable-slash-commands --no-session-persistence --output-format stream-json --verbose`.
- **`--tools` is variadic,** so the empty value must be its own list element, `""` (it reaches `claude.exe` as an empty argument), followed straight away by another flag, as v1's command.py does for its lists.
- **Where it runs:** an empty cwd, `.state/assignment-check/reader/`, with a 10-minute kill.
- **Probe.** `--tools ""` is in `claude --help` for 2.1.304, but v1's flags were probed on 2.1.301. The phase 0/1 probe confirms that the init event's tools are exactly `{StructuredOutput}`.
- **Init check:** the mode is `dontAsk`, the tools are exactly `{StructuredOutput}`, there are no MCP servers, and the cwd is that folder.
- **Size.** The run context is capped at `MAX_READER_CHARS = 240000` (about 60k tokens). One reader runs per site (Moodle, then Classroom).
  - Moodle's 9 pages at the 25,000-char snapshot cap come to 225,000 at most, so whole-page cuts should never happen in normal use.
  - If a site is still over the cap, it's cut by whole pages, the cut pages are reported as unreadable, and a log warning names them.
  - Phase 0's page sizes confirm both caps.
- **Prompt:** `refdocs/routines/assignment-check-reader.md`.
- **Run context:**
  - a trusted line with the date and time;
  - the page list (key, site, course tag), written by the runner;
  - every `ok` page's text, all in one `signal_untrusted.framed(line, pages, "untrusted_site_content")`.
- **Output:**
  - `pages[]` of `{key, readable, account}`;
  - `items[]` of `{page, name, class_name, kind, due, status_text, ref}`, where `class_name` is the Classroom class as the page shows it (empty on Moodle), `kind` is `assignment`, `quiz`, `event` or `classwork`, `due` is `YYYY-MM-DD HH:MM`, `YYYY-MM-DD` or empty, and `ref` is the Moodle `id` from `/mod/<type>/view.php?id=<n>` or the Classroom item id;
  - `suspicious[]`: the keys of pages with text aimed at an assistant.

### 3.3 Validation (`assignment_check/findings.py`, pure)

This is the boundary between page text and `life/`. Each rule drops the item, or the page, and logs it with `%r`:

- **Page.** `page` must be one of this run's `ok` keys. The course tag comes from the runner's config for that page, never from the model.
- **Name.** At most 120 characters, and it must pass v1's character allowlist and `FORBIDDEN` from `kb/line_rules.py` (no URLs, no `]:`, no character references, no numbers of 6+ digits). It must also occur in that page's text, compared whitespace-normalised and casefolded. So the reader can't invent items.
- **Ref.** It must appear in that page's `/url:` lines in the expected shape.
  - The runner builds the link itself: `https://lms.example.edu/mod/<type>/view.php?id=<n>`, or `https://classroom.google.com/u/N/c/<class>/a/<id>/details` **[unverified]**. A URL the model wrote is never used.
  - Links go to `.state/assignment-check/last-check.json` and the foreground output.
- **Status** is set by the runner, never the model:
  - **Classroom:** from which list the item is on (not-turned-in, missing or turned-in).
  - **Moodle:** from a fixed table of Moodle phrases ("Submitted for grading", "No submission", "Draft (not submitted)" **[unverified]**), and only when `status_text` sits on the same snapshot line as the name. A Moodle table row's accessible name holds all its cells **[unverified]**.
  - Otherwise it's `unknown`. So text elsewhere on a page can't mark work as submitted.
- **Due.** It must parse, or it's left empty.
- **Class.** On Classroom, the course tag comes from matching `class_name` against `courses.py`. That name must also occur in the page text, and an item with no match is dropped.
- **Account.** A Classroom page is dropped unless the configured `[classroom] account` occurs in its text, checked by the runner. The reader's `account` field is only logged, never trusted. The `/u/N` index can change.
- **Suspicious.** A page in `suspicious` loses all its items.
- **Caps.** 60 items per page, 150 in all.
- **Flags.** Last, the runner works out `overdue` (due before now, and not submitted or graded) and `due_soon` (due within 24 h).

### 3.4 Writer

- **Lockdown.** v1's argv minus the mail server:
  - the cwd is `life/`;
  - `--restricted`, and `--tools Read,Edit`;
  - `--allowedTools Read` plus the exact `Edit(/<path>)` rules from `kb.find_targets`;
  - v1's `DISALLOWED_TOOLS`;
  - `--strict-mcp-config` with no MCP servers, a $1.00 budget and a 15-minute kill.
- **Init check:** the tools are exactly `{Read, Edit, StructuredOutput}`, with no servers.
- **Prompt:** `refdocs/routines/assignment-check-writer.md`. Its line rules and KB conventions are mail-digest.md's, with the tag `(site)`. Move those two sections into one file both routines load, rather than copying them.
- **Run context:**
  - v1's targets;
  - the check time;
  - per-course page problems, such as "Moodle: login needed", so the writer never concludes there's nothing due;
  - the validated items, in one `untrusted_site_content` frame.
- **Rules:**
  - Update an existing line, including the digest's `(mail)` lines, rather than add a second one. A changed line ends in ` (site)`.
  - Overdue items go under `## Overdue`, in v1's format.
  - Submitted or graded items are ticked, with `(turned in per Moodle 2026-10-20) (site)` (decided).
  - Never untick and never delete. This is also enforced, not just prompted. On a site run (`forbid_untick=True`), `line_rules.edit_problems` counts per file, before and after:
    - the todo lines (`- [ ]` and `- [x]`), whose count mustn't drop;
    - the `- [x]` lines, whose count mustn't drop.

    Counting, rather than pairing removed and added lines, means a tick (a `[ ]` line replaced by an `[x]` line) and a move under `## Overdue` both pass. A file whose net todo count or net ticked count drops is undone like any other rule break.

    The check is net-only. One untick plus one tick in the same file passes, and so does a delete plus an add. It stops the bulk case, such as wiping or unticking a section, not a matched swap. The 4-change budget and the guard's 5-line cap bound what a swap can touch, and the digest email and `git diff life/` show it. The digest's rules stay as they are.
  - An `unknown` status changes nothing.
  - A course whose page failed is left alone.
- **The 5-line cap.** `edit_problems` allows at most 5 changed or removed lines per file (`MAX_REMOVED_LINES_PER_FILE`, where a changed line counts as both). The first check changes about 7 lines in this week's `plan.md`, so it must not try them all at once.
  - **Chosen strategy:** keep v1's cap and spill, and let later checks converge.
    - **One rule:** the runner sorts the items by priority (overdue, then due soon, then status changes, then new items), and passes the writer at most 4 status-changing items in all, the first 4 in that order across every course, plus new items, capped at 20 in all.
      - 4 stays under the 5-line limit even if all 4 land in `plan.md`, as overdue lines do in its one `## Overdue` section.
      - The plan therefore doesn't depend on the model staying under the 5-line limit. An over-budget writer would have its edit undone, and the review flag set then blocks the digest too.
    - New items it can't place go to `inbox.md` as new lines, as v1's routine already does.
    - Changes left over (mostly ticks, which can't be spilled) aren't stored anywhere. Each check rewrites from the site's current state, so the next check makes the next 4. The done line says "3 more updates next check".
  - **Why not the alternatives:**
    - A larger cap for site runs weakens the one guard limit that protects the owner's own lines, and v1 tuned it for exactly that.
    - Splitting the writer into passes costs one claude run per pass, and steered input could use them all up.
    - The backlog only happens once (this term's first check). After that, a check changes a line or two.
- **Returns** only `summary` (logged with `%r`). The runner writes the announcements.
- **Skipped** when no item passes validation.

## 4. Pages per site

| Site | Page (per course) | Gives |
|---|---|---|
| Moodle | `/mod/assign/index.php?id=<course>` | Every assignment: name, due date, submission status, grade. The main source of status |
| Moodle | `/mod/quiz/index.php?id=<course>` | Quizzes and their close dates. Status stays `unknown` |
| Moodle | `/calendar/view.php?view=upcoming&course=<course>` | Other due events (forums, external tools). No status |
| Classroom | `/u/N/a/not-turned-in/<classId>`, `/u/N/a/missing/<classId>`, `/u/N/a/turned-in/<classId>` **[unverified]** | Assigned, missing and done work for that one class. If phase 0 finds that only the `/all` forms work, use those. The class name check in 3.3 (the class name from the config) then does the filtering |

Three pages per course. Course ids and class names live in the gitignored `tools/mail-digest/assignment-check.toml`, edited each term (`setup config mail-digest`).


## 5. Login and Duo

- **Moodle.** Each run starts a fresh Edge, and the Moodle and CAS cookies are session cookies, so every check needs a CAS login. That takes three steps from the owner:
  - the vault's Allow dialog, which denies by itself after 60 s;
  - Windows Hello;
  - Duo.
- **Duo.** The browser tool's watcher speaks "Duo push for sso.example.edu, approve on your phone", and, as decided, it also reads out the Verified Push code. Clicks inside Duo stay locked.
  - On the first run, the owner clicks Duo's "trust this browser". Later runs may then skip Duo for as long as the school remembers the device **[unverified]**.
- **Google.** Its cookies are persistent, and sign-in is never automated. If Classroom lands on `accounts.google.com`, the run asks the owner to sign in themselves in a normal browser window on the checker profile, and the checker reuses that profile's session.
  - The owner signs in by hand in a normal browser window: plain Edge started with `--user-data-dir` pointing at `tools/browser/.profile-checker`. It's a once-a-term step.
- **The owner isn't there.** The vault dialog denies after 60 s, so no password is sent and no Duo push goes out.
  - The Moodle pages get `login_needed`, and Classroom is still checked.
  - The hub says "Moodle needs you at the PC to log in. Ask again when you're there."
  - Nothing retries, and nothing is scheduled.

**Owner steps (one-time):**

1. **Vault username.** The credential is `school`, with origin `https://sso.example.edu`. Check that its username is your school login.
   - In a terminal (not through Claude), run `uv run --project tools/vault vault list`.
   - If the username is wrong, run `vault remove school`, then `vault add school --name the school --origin https://sso.example.edu --username <your school login>`.
   - `login_credential = "school"` goes in `browser-checker-moodle.toml`.
   - **A conscious exception.** `password-vault.md` section 5 and `vault/cli/exclusions.py` exclude SSO and identity accounts, and CAS is the school's SSO. Storing it is an exception the owner confirms. `vault add` doesn't warn about it today: its SSO keywords don't match `school` or `sso.example.edu`. Phase 1 adds a `cas` keyword to `exclusions.py`, a small item that needs the owner's review like any vault change.
   - The vault README says Windows Hello is untested end to end. Phase 0's spike tests it with one fill from a process started the way `--now` starts one (pythonw, then `uv` with `CREATE_NO_WINDOW`), and phase 4 repeats it with the real `--now`. Whether Hello's prompt shows from a detached process is unproven.
2. **Google.** First, one `LocalBackend` launch on `.profile-checker/`, from the phase 0 spike, creates the folder and runs `disable_password_saving` on it. Then the owner runs the plain-Edge command above the owner, with no checker run going, and signs the school Google account in as account 1, once.
   - In that window the owner declines Edge's offers to save the password, and to sign in or sync with a Microsoft account.
3. **First CAS login** (the phase 0 spike's fill). Approve Duo, then click "trust this browser".

## 6. Reuse of v1

Everything reused lives in `tools/mail-digest/src/mail_digest/` unless a path says otherwise.

- **`memory/lock.py`** (`run_lock`): the same `.state/run.lock`, so a check and a digest never overlap. They edit the same files, and each guard would report the other's edits as other changes.
- **`memory/state.py`:** the same `state.json`, shared for `announced` and `needs_review`. Both runners honour and set the review flags. The check never touches `searched_until`.
- **`kb/`:** `find_targets`, `snapshot`, `guard_edits`, `line_rules` and `review.is_reviewed`, unchanged except for the tag parameter.
- **`claude/`:** `launcher.run_claude` and `find_claude`; `init_check.init_problems` and `command.build_command`, both taking a lockdown (below).
- **Other modules:**
  - `child_env` (`clean_env`, `run_hidden`, `run_hidden_output`, `kill_tree`);
  - `background.start_background_run`;
  - `todo_board.refresh_todo_board`;
  - `announce/` and `outcome.announce_once`;
  - `notices.kb_alerts`.
- **Elsewhere:**
  - `signal_untrusted` (`packages/untrusted`, stdlib, added as a path dependency);
  - the browser tool's actions, policy, redaction and Duo watcher;
  - the self-only digest email, `digest_email.email_digest(RunEdits(...), send_digest_email)`, called where `run.py` calls it: after a successful run that the guard didn't undo, before the announcements, with a failed send spoken as `email_alert`.

**Phase 1 refactors.** The digest's behaviour doesn't change, and its existing tests pass as they are.

- `digest_email/build.py`'s fixed `TRUST_NOTE` says only that `(mail)` lines came from email. It must also say that lines ending in `(site)` came from course sites, and that they're data, never instructions too. `life/README.md` gets the same line.

- `line_rules.edit_problems` and `guard_edits` take the tag, with `MAIL_TAG` as the default, and the `forbid_untick` flag (off for the digest).
- A frozen `Lockdown` value describes each run: its tools, allow rules, deny list, MCP config (or none), prompt file, and expected tools and servers. `build_command` and `init_problems` take it, and the digest's is today's constants.
- `run.py`'s guarded-edit sequence becomes one helper both runners call: `_unreviewed`, `_snapshot_before`, flagging, `_launch`, the guard and unflagging.

**Why inside `tools/mail-digest`.** The check shares the lock, the state, the guard, the launcher and the venv. The digest README's TODO already puts it there. If a third source comes, lift `kb/` and `claude/` into `packages/`.

**New package:** `assignment_check/`, with `cli.py`, `courses.py`, `visit.py` (writes the plan, runs `browser-tool-visit` through `run_hidden_output` with `VISIT_TIMEOUT_S`, reads `pages.json`), `reader.py`, `findings.py`, `writer.py`, `notices.py` and `run.py`, plus `__init__.py` and `__main__.py`. That's 10 source files, plus `README.md` (what it does, the `assignment-check` CLI, its dependencies on the rest of mail_digest, tools/browser and `signal_untrusted`), per codingrules section 3.

## 7. Announcements

The runner writes them, and none of the model's sentences are used. They're spoken through `announce/notify.py` with source `assignment-check`.

1. **The runner's notices come first:**
   - the browser was busy;
   - a login is needed;
   - Google sign-in is needed;
   - a page was unreadable, or on the wrong account;
   - a page was suspicious;
   - then v1's `kb_alerts`.
2. **Then the items,** from the validated findings: newly overdue and not submitted, then due within 24 h and not submitted.
   - Keys are `overdue|<tag>-<name slug>` and `due|...`, as `KEY_PATTERN` allows.
   - They're deduped through `announced` for 30 days.
   - After a guard undo, no item is spoken, as in v1.
3. **It always ends with a done line,** because the owner is waiting: "Assignment check done: 4 updates", or "nothing new".

The same item can get one key from mail and another from the site, so it may be spoken once by each. That's accepted.

## 8. Failure modes

| Failure | Result |
|---|---|
| Profile busy (the plain-Edge sign-in window is open on `.profile-checker/`) | No claude runs. "The checker's browser is open. Close it and ask again." The desktop MCP browser no longer conflicts |
| Digest running (lock held) | `--now` refuses: "The mail digest is running, try again in a minute" |
| Vault missing, locked or denied; `origin_mismatch`; Duo times out | Moodle pages get `login_needed`, and the rest still runs |
| Classroom on `accounts.google.com`, or `account` isn't the school one | Classroom is skipped, with the matching notice |
| A page is unreadable, truncated or changed layout | The reader marks it `readable: false`. Its course isn't touched, and the run says which site |
| `pages.json` missing or unparseable (for example after the timeout kill) | Treated as `error`: no claude runs, and a failure notice is spoken |
| Reader output malformed, over budget, timed out, or its init check fails | No writer runs, and a failure notice is spoken |
| A suspicious page | Its items are dropped and its key is logged |
| Writer guard undo, or other files changed | v1 behaviour: rejected copy, alert, review flags |
| A Claude Code update changes a flag | The init check kills the run |
| An asset host is missing from the allowlist | The page may render without it. Blocked hosts are in the browser log |
| Hub down | v1 behaviour: keys stored only once queued |

## 9. Tests (AGENTS section 6)

Fakes only. No real sites, claude or hub. Parametrize the security tables.

- **browser visit** (`*.localhost` fixtures, like the existing browser tests):
  1. A plan URL off the allowlist, or a lookalike host, refuses the whole plan before launch.
  2. Fill rules, in one table:
     - a Moodle target redirected to the login host calls a fake filler once, with the configured id and `submit=True`;
     - a config without login keys (the Classroom launch) never fills, even on the login host;
     - a host not in `[visit]` is never filled;
     - a Moodle target that reaches CAS by a JavaScript navigation, with no `service` on `lms.example.edu`, isn't filled;
     - `denied` gives `login_needed` while the other targets go on.
  2a. Per launch, in one table, with fixture hosts standing in for the real ones:
     - under the Classroom config, a navigation to the CAS stand-in is refused by policy;
     - under the Moodle config, a navigation to a Google sign-in stand-in is refused by policy;
     - under the Moodle config, a Moodle URL that 302s to a Google stand-in is refused, by the resolver rules on the hop;
     - under the Classroom config, a Google stand-in that 302s to the CAS stand-in is refused on the hop, and the target is `google_signin_needed`;
     - at the Classroom launch's start, a host-only cookie on the CAS stand-in, a `.cas.<stand-in>` cookie and a `.<parent stand-in>` cookie are seeded, then `BrowserSession.clear_cookies` runs, and `context.cookies()` shows all three gone;
     - after a fill, a context close ends the launch: no relaunch, and the remaining targets get `error`.
  2b. The committed configs, checked through `HostPolicy.check_host` as the hard rules in 3.1 describe, plus their `allow_all`, `deny` and `use_system_proxy` pins.
  3. A launch failure gives `busy`, and the out file is still written.
  4. **Scrub:** a fake filler reports a filled value, and the fixture page echoes it into its text and into an error. The value never reaches the out file or the log.
- **`findings.py`** (a security table): an invented name, a ref missing from the page's URLs, a status text off the name's line, bad characters or a URL or 6+ digits in a name, a Classroom page on the wrong account, a suspicious page, and the caps.
- **The lockdowns** (one table): the reader and writer argvs, and an init event with an extra tool, an MCP server or the wrong mode kills the run. The digest's lockdown argv is unchanged.
- **`line_rules`:** add cases to the existing parametrize:
  - a `(site)` line passes on a site run, and a `(mail)` line fails;
  - with `forbid_untick`, an `[x]` to `[ ]` change or a removed todo line fails, while a tick and a todo moved under `## Overdue` pass.
- **`assignment_check/run.py`** with fakes:
  - busy starts no claude;
  - a failed reader starts no writer;
  - a guard undo speaks no items;
  - success refreshes the board and calls the email step.

No tests for prompt wording, `courses.py` constants or CLI glue.

## 10. Phases

| Phase | What | Effort |
|---|---|---|
| 0. Owner setup and spike | With the owner present. The steps are listed below the table | ~0.5 day |
| 1. Shared pieces | Section 6's refactors in mail-digest (the digest's tests pass unchanged), plus the `cas` keyword in `tools/vault/src/vault/cli/exclusions.py`, which needs the owner's review like any vault change | ~1 day |
| 2. Visit mode | After the backends refactor and the docker backend land. `browser_tool/visit/`, `[visit]` settings, the `browser-tool-visit` script, `allow_relaunch`, `BrowserSession.clear_cookies`, the two checker configs (both with `profile_dir = ".profile-checker"`), tests | ~1.5 days |
| 3. The checker | `assignment_check/`, both routines and the shared line-rules file, the entry point, the voice-prompt line, the `life/README.md` line, and a pointer replacing the digest README's TODO. Tests | ~2 days |
| 4. Live run | Run the real `--now` with the owner (this repeats the detached Hello check), then trim the reader prompt on what it misses | ~0.5 day |

**Phase 0 steps.** With the owner present. **First,** commit the `.gitignore` line `tools/browser/.profile-checker/`, before the folder exists. Then a throwaway spike script (not committed) builds an `ActionContext` on `.profile-checker/` from draft configs, ahead of phase 2's visit mode. It does:
1. one launch, to create the folder and turn off password saving;
2. section 5's Google sign-in, which the owner does by hand in a normal browser window;
3. after owner step 1 (the vault username fix), one CAS fill from a detached process started as `--now` starts one (the Hello test), in which the owner approves Duo and clicks "trust this browser";
4. a draft visit of each section 4 page, recording:
   - that the URLs work;
   - the row and list shapes in the snapshots, and the status wording;
   - the Classroom item URL form and account label;
   - page sizes;
   - the real CAS cookies' names and domains (never values), whether any is a Duo trust cookie (3.1), and that the clear's pattern covers the CAS ones;
5. per launch, that the other site's sign-in host is refused: CAS from Classroom, and `accounts.google.com` from Moodle;
6. that Startup boost doesn't touch this folder;
7. whether the Moodle launch needs the wait for a lingering `msedge.exe`;
8. a draft-allowlist run, to collect blocked asset hosts from the browser log, with Classroom's never including `*.google.com` or `www.google.com`.

The owner is told that a Hello or passkey prompt arriving without the vault's Allow dialog first isn't the checker's, so the owner shouldn't approve it.

Total about 5.5 days. Phase 2 can run alongside phase 1.

## 11. Decided

The owner accepted the proposed defaults, among them:

3. **Ticking:** yes. A todo is ticked when Moodle shows "Submitted for grading" or Classroom lists it as turned in, noted "(turned in per Moodle <date>) (site)". A check never unticks.
4. **Duo code relay:** on for `sso.example.edu`, in the checker's config only. The relay names a Duo prompt after the page the navigation into Duo came from, by that navigation's `Referer` (here CAS's own form POST). It relays only when that page is on `sso.example.edu` and the path to Duo didn't pass through another host.
5. **Grades:** not recorded in v2. Due dates and status only.

## Risks

- **Index-page assumptions.** If the school's Moodle themes hide status on the index page, Moodle status stays `unknown` until v2 reads each assignment's page. That's a bounded later change: one more page per item, with the same validation.
- **Three approvals per run.** The vault dialog, Hello and Duo for every check may feel heavy. The checker profile is new and holds no restore-session setting unless someone sets one in plain Edge. Either way, its CAS cookies stay in `.profile-checker/`, away from the desktop browser (3.1).
- **An Edge window appears** on the owner's screen for a minute or two during each check. That's the cost of a local, headed Edge, since docker jobs have no logins.
- **The writer still has Edit,** as v1's model does. Its input is now short, validated fields rather than whole pages, and the guard caps what it can change.
