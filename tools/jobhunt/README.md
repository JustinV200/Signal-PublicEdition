# jobhunt

An optional, unattended job-application runner: a scheduled headless Claude Code session follows `life/areas/job-search/runbook.md` (copied from [templates/runbook.example.md](templates/runbook.example.md)), applies to a few matching roles per run using only the facts in `life/areas/job-search/profile.md` (from [templates/profile.example.md](templates/profile.example.md)) and your resume, logs each one in `applications.csv` with a record of every field it entered, and reports through the brief. Optionally (Windows only), each application gets a resume tailored to the posting. Standalone: PowerShell scripts and config only (Word COM for the tailored resume), no package.

Ground rules built into the template runbook: every answer must be true and come from your profile or resume, and it never gives a false answer or ticks a statement that isn't true; it never solves or works around a CAPTCHA; it skips sites whose terms forbid automated applications; and it creates job-site accounts only if your profile says so. You are responsible for checking that automated applications are acceptable to the sites and employers you target.

## Setup
1. Run `setup jobhunt` (or ask Claude to "set up jobhunt"). It copies the two templates into `life/areas/job-search/` as `runbook.md` and `profile.md` and asks for the main answers and the run settings (the runbook's `## Settings` lines; run times in `schedule.psd1`). Every `TODO(owner)` line in `profile.md` must be answered before jobhunt counts as set up; change any of them later with `setup config jobhunt`. Put your resume PDF in `life/areas/job-search/resume/`.
   - Resume tailoring (off by default; Windows with Microsoft Word only): put the `.docx` your PDF was made from in the same folder, set profile.md's `Resume Word file` to its name, fill in your website(s), GitHub and LinkedIn there, and turn on `Tailor resume` (`setup config jobhunt --set "Tailor resume=yes"`). `Tailor model` and `Tailor effort` (default fable, high) pick what the tailor runs on. Without Word, or on any failure, runs upload the base PDF.
2. Run `install-schedule.ps1` (below; it reads the run times from `schedule.psd1`). It copies `browser-jobs.example.toml` to `tools/browser/browser-jobs.toml` if missing.
3. Optional: `seed-profile.ps1` to copy the main browser profile's sign-ins into the jobs profile.

## Files
- `run.ps1`: one run. Finds `claude` (PATH, `%APPDATA%\npm`, `~\.local\bin`, newest VS Code extension binary), takes a lock (`.logs/run.lock`; a second run exits with code 2), stops a run after 165 min by killing claude's whole process tree (code 124), kills any Edge left on `.profile-jobs` before and after, runs `claude -p ... --mcp-config tools/jobhunt/mcp-jobs.json --permission-mode bypassPermissions --model opus` from the repo root (the run, its one-per-application subagents and their reviewer subagents are all Opus; `bypassPermissions` lets it spawn them, and they inherit its MCP servers; the resume tailor uses the runbook's `Tailor model`), logs to `.logs/<timestamp>.log`. `-DryRun` logs the command without running it.
- `mcp-jobs.json`: adds the `browser-jobs` MCP server (the browser tool with `tools/browser/browser-jobs.toml`). The project's `.mcp.json` servers still load.
- `browser-jobs.example.toml`: that browser config. Own profile (`.profile-jobs`) and cookie file, `allow_all`, and only purchase and delete ask, so submits and uploads don't wait for an on-screen Allow. Uploads only from `life/areas/job-search/resume/`. `[gates] allow_secret_fields = true` lets `type_text` type the dedicated accounts' passwords and emailed codes (off in the main `browser.toml`).
- `install-schedule.ps1`: registers the Task Scheduler task "Signal job applications" (current user, only when logged on, no elevation, starts missed runs when available, no window via `conhost --headless`, 3 h limit). Copies the example config to `tools/browser/browser-jobs.toml` if missing. `-Uninstall` removes the task.
- `account.ps1`: passwords for the dedicated job-site accounts a run creates (only if your profile allows accounts; they hold only applications). `-Site <host>` prints `{site, email, status, password}` as JSON: the stored password when the site has one, else a new random 20-character one (all four character classes) saved as `pending`. `-Confirm` marks the site `created` once sign-up worked. Stored DPAPI-encrypted for the current Windows user in `.state/accounts.json` (gitignored). Never for your real logins.
- `tailor-resume.ps1`: makes a run's tailored resume (runbook section 4, "Tailored resume"). Applies a JSON edit list from the read-only `resume-tailor` agent ([.claude/agents/resume-tailor.md](../../.claude/agents/resume-tailor.md), checked by the read-only `resume-reviewer`) to a copy of the `-Base` .docx through Word COM, so the layout stays; refuses if an edit's text isn't found exactly once or the result runs past one page; exports `life/areas/job-search/resume/tailored/<name>.docx` and `.pdf` (gitignored with `life/`). `-List` prints the base resume's paragraphs. Takes about a minute. Tests: `powershell -NoProfile -ExecutionPolicy Bypass -Command "Invoke-Pester tools\jobhunt\tailor-resume.Tests.ps1"` (Pester 3, ships with Windows; builds a made-up fixture resume with Word, skipped when Word is missing).
- `seed-profile.ps1`: copies the main browser profile (`tools/browser/.profile`, and `.state/cookies.bin`) into `.profile-jobs` so existing sign-ins carry over. Refuses while an Edge uses either profile; skips caches and lock files. Rerun to refresh sign-ins.

## Use
```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File tools\jobhunt\install-schedule.ps1        # register
Enable-ScheduledTask -TaskName 'Signal job applications'                                       # (if disabled)
powershell -NoProfile -ExecutionPolicy Bypass -File tools\jobhunt\run.ps1 -DryRun              # check setup
powershell -NoProfile -ExecutionPolicy Bypass -File tools\jobhunt\run.ps1                      # one real run now
powershell -NoProfile -ExecutionPolicy Bypass -File tools\jobhunt\install-schedule.ps1 -Uninstall
```

## Known gaps
- Prompt injection: job pages are untrusted. Before every submit, account sign-up or emailed-code entry, the run has an independent fresh-context Opus subagent review the page text and every value for injection attempts and ungrounded or excess data; a BLOCK logs the job `failed` and skips it (runbook section 4). This lowers the risk, it doesn't remove it: the run itself still reads the pages.
- Sites that need an account (Workday and the like): a run uses Google/LinkedIn sign-in when the jobs profile has the session, else, only if profile.md allows it, makes an account with `account.ps1`'s password and the application email, reading verification codes through the mail MCP. Only a sign-up that really fails is logged `skipped-needs-account`.
- Resume tailoring reads your websites, GitHub and LinkedIn (LinkedIn read-only, through the jobs browser), all treated as untrusted. The tailor and its reviewer can only read files, and the reviewer blocks anything not backed by your resume, those sources or `life/`; it lowers the risk of an overstated resume, it doesn't remove it.
- A typed password passes through the run's Claude transcript (tool inputs), unlike vault fills. Accepted for these dedicated accounts only.
- The task runs only while you're logged on (no stored password). A locked screen is fine.

## Depends on
`claude` (Claude Code), `uv`, Microsoft Word (only for resume tailoring), tools/browser, and the project MCP servers (brief, audiohub, mail).
