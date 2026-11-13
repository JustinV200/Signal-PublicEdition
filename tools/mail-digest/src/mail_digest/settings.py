"""Tunable values for one mail digest run, kept in one place.

The schedule (run time, task name) lives in tools/mail-digest/schedule.psd1, because
only register.ps1 needs it. Everything the run itself needs is here. Every other
module of the package may import from this one; it imports nothing from them.
"""

from pathlib import Path

# tools/mail-digest (this file is src/mail_digest/settings.py) and the repo root.
TOOL_ROOT: Path = Path(__file__).resolve().parents[2]
REPO_ROOT: Path = TOOL_ROOT.parents[1]

# The job's working directory. --restricted confines every file tool to it.
LIFE_DIR: Path = REPO_ROOT / "life"
ROUTINES_DIR: Path = REPO_ROOT / "refdocs" / "routines"
# The routine's rules. The runner appends the shared line rules and KB conventions to
# it (claude/prompt.py) and passes the result as --append-system-prompt-file.
PROMPT_PATH: Path = ROUTINES_DIR / "mail-digest.md"
SHARED_RULES_PATH: Path = ROUTINES_DIR / "kb-line-rules.md"
# The job's own MCP config: only the mail server.
MCP_CONFIG_PATH: Path = TOOL_ROOT / "mcp.json"

# Gitignored (tools/mail-digest/.state/). Only this runner writes here; the model can't.
STATE_DIR: Path = TOOL_ROOT / ".state"
STATE_PATH: Path = STATE_DIR / "state.json"
LOCK_PATH: Path = STATE_DIR / "run.lock"
LOG_PATH: Path = STATE_DIR / "mail-digest.log"
# claude's stderr, overwritten each run (a file, so a full pipe can't stall the run).
CLAUDE_STDERR_PATH: Path = STATE_DIR / "claude-stderr.log"
# The composed system prompts (claude/prompt.py), rewritten before each run.
PROMPTS_DIR: Path = STATE_DIR / "prompts"
DIGEST_PROMPT_PATH: Path = PROMPTS_DIR / "mail-digest.md"
WRITER_PROMPT_PATH: Path = PROMPTS_DIR / "assignment-check-writer.md"
# Where the KB guard keeps the text of edits it undid.
REJECTED_DIR: Path = STATE_DIR / "rejected"
LOG_MAX_BYTES = 1_000_000
LOG_BACKUP_COUNT = 2

# Mail tool aliases to digest (see tools/mail/SETUP.md). One missing from
# `mail accounts` is skipped quietly; one that isn't `ok` is reported.
ACCOUNT_ALIASES: tuple[str, ...] = ("personal", "alt", "school")

# Claude run limits. The budget is a hard per-run stop (claude --max-budget-usd).
MODEL = "sonnet"
MAX_BUDGET_USD = "2.00"
# Kill a hung run. schedule.psd1's TimeLimitMinutes is a longer backstop.
RUN_TIMEOUT_S = 30 * 60

# How far back to search: on an account's first run, and at most ever (so an
# account that was offline for a week doesn't pull a week of mail in one run).
FIRST_RUN_LOOKBACK_S = 2 * 24 * 3600
MAX_LOOKBACK_S = 3 * 24 * 3600
# Each window starts this long before the last one ended, so mail stamped right at
# the boundary isn't missed. The routine skips items already in the KB.
SEARCH_OVERLAP_S = 5 * 60

# Announcements: the runner, not the model, speaks them through the audiohub CLI.
AUDIOHUB_PROJECT: Path = REPO_ROOT / "tools" / "audiohub"
# After a successful run the runner refreshes the whiteboard's TODO view (best effort).
WHITEBOARD_PROJECT: Path = REPO_ROOT / "tools" / "whiteboard"
BOARD_SYNC_TIMEOUT_S = 30
NOTIFY_SOURCE = "mail-digest"
NOTIFY_PRIORITY = "high"
NOTIFY_TIMEOUT_S = 60
# Items spoken per run; the rest are summed up in one "plus N more" sentence.
MAX_SPOKEN_ITEMS = 3
# One spoken item from the model is cut (at a word break) to about this long.
MAX_SENTENCE_CHARS = 120
# Announced keys (what was already spoken) are forgotten after this long, and at
# most this many are kept (the newest).
ANNOUNCED_KEEP_S = 30 * 24 * 3600
MAX_ANNOUNCED_KEYS = 500
# An announcement the hub didn't take is retried on later runs for this long: a
# due-within-24-hours item is stale after that.
PENDING_KEEP_S = 24 * 3600
# Speak a failure alert every this many consecutive failed runs.
FAILURE_ALERT_EVERY = 2

# The digest email (digest_email/): after each successful run the runner mails the
# owner the open todos and the run's new lines through the mail tool's self-only
# `mail send-self` (tools/mail/src/mail_tool/service/self_send.py).
MAIL_PROJECT: Path = REPO_ROOT / "tools" / "mail"
MAIL_SEND_TIMEOUT_S = 60
# The body file send-self reads, overwritten each run (so the last one sent stays readable).
DIGEST_EMAIL_PATH: Path = STATE_DIR / "digest-email.txt"
# Kept under send-self's own 100,000-char cap, so a big catch-up run is cut, not refused.
MAX_EMAIL_BODY_CHARS = 50_000

# Step 2 in code (mailbox/): the runner lists the accounts and searches each window
# through the mail tool's CLI, then hands the model the messages it found.
MAIL_CLI_TIMEOUT_S = 120
# Results per search. A page this full (less the slack) means there may be more, so
# the next search pages back from its oldest date (the CLI has no cursor). The slack
# covers messages the mail tool drops when they're deleted mid-search.
SEARCH_PAGE_SIZE = 50
SEARCH_PAGE_SLACK = 5
# Searches per account per run, about 45 messages each. Past this the account isn't
# completed this run (logged and spoken), so a mail flood can't page forever.
MAX_SEARCHES_PER_ACCOUNT = 40

# Step 5 in code (deadlines/): open todos due within this many hours are announced.
DUE_SOON_HOURS = 24

# Caps on the model's structured output, which untrusted email shapes.
MAX_OUTPUT_ITEMS = 20
MAX_SUMMARY_CHARS = 2000

# The KB guard (kb/guard.py): every line the digest adds carries this tag.
MAIL_TAG = "(mail)"
MAX_ADDED_LINE_CHARS = 300
# Lines added or changed in one file per run, blank ones included. A daily run adds
# a handful per file, and a 3-day catch-up or a syllabus email full of deadlines
# maybe 20 to 30. Past twice that it's more likely an email steering the model into
# burying the KB, and the guard undoes the file.
MAX_ADDED_LINES_PER_FILE = 60
# Existing non-blank lines changed or deleted in one file per run (a changed line
# counts as removed, so ticking a todo uses one). Rewriting the owner's lines is the
# risky edit, so this stays small; the routine adds the rest to inbox.md instead.
MAX_REMOVED_LINES_PER_FILE = 5

# Checker v2 (assignment_check/, refdocs/research/checker-v2.md): an on-demand read of
# the course sites. It shares the lock, the state file and the KB guard above.
CHECK_DIR: Path = STATE_DIR / "assignment-check"
# The owner's sites and courses (gitignored; setup copies assignment-check.example.toml).
CHECK_CONFIG_PATH: Path = TOOL_ROOT / "assignment-check.toml"
CHECK_LOG_PATH: Path = CHECK_DIR / "assignment-check.log"
# The validated items with their links, for the owner (links can't go into life/).
LAST_CHECK_PATH: Path = CHECK_DIR / "last-check.json"
# The reader runs in this empty folder, so --restricted leaves it no files to read.
READER_DIR: Path = CHECK_DIR / "reader"
READER_STDERR_PATH: Path = CHECK_DIR / "reader-stderr.log"
WRITER_STDERR_PATH: Path = CHECK_DIR / "writer-stderr.log"
# The reader writes nothing, so its routine is passed as it is.
READER_PROMPT_PATH: Path = ROUTINES_DIR / "assignment-check-reader.md"
WRITER_ROUTINE_PATH: Path = ROUTINES_DIR / "assignment-check-writer.md"
BROWSER_PROJECT: Path = REPO_ROOT / "tools" / "browser"
# Each browser-tool-visit launch is killed after this. The Moodle launch's worst case
# (vault dialog, Hello, the 150 s login wait, 9 pages x 38 s) is about 10 minutes.
VISIT_TIMEOUT_S = 15 * 60
CHECK_MODEL = "sonnet"
CHECK_BUDGET_USD = "1.00"
READER_TIMEOUT_S = 10 * 60
WRITER_TIMEOUT_S = 15 * 60
# One reader's run context, about 60k tokens. Moodle's 9 pages at the 25,000-char
# snapshot cap come to 225,000, so whole-page cuts should only happen if a page grows.
MAX_READER_CHARS = 240_000
# Every line the checker adds or changes carries this tag.
SITE_TAG = "(site)"
CHECK_NOTIFY_SOURCE = "assignment-check"
