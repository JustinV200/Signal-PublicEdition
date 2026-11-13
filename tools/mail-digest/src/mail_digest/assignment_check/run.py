"""One assignment check, start to finish: visit, read, check, write, then the v1 steps after.

run_check takes its outside world (paths, the visit launches, the two claudes, notify,
the mail sender, the board, the clock, git) as CheckDeps, so tests run it with fakes.
The caller holds the run lock the mail digest uses too.

1. gather.py: both visits, then one reader per site. A busy or failed launch, or a
   failed reader, stops the check before the writer, with its reason spoken.
2. findings/: the runner's own checks of what the readers said (pure).
3. The writer, only when the 4-change budget leaves it something to do, through the
   v1 guard with the (site) tag and no unticking (steps.run_guarded_edit).
4. The announcements (notices.py), then on success the digest email (unless the
   guard undid an edit) and the whiteboard's TODO view.
It shares the state file's review flags and announced keys with the digest, and never
touches its search windows or failure count. It never commits.
"""

import logging
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from datetime import datetime
from pathlib import Path

from mail_digest.announce import Announcement
from mail_digest.assignment_check.courses import CheckConfig, Page
from mail_digest.assignment_check.findings import Findings, check_findings
from mail_digest.assignment_check.gather import GatherDeps, gather
from mail_digest.assignment_check.notices import (
    CHECK_NAME,
    CRASHED,
    done_line,
    item_notices,
    problem_notices,
    stopped_line,
)
from mail_digest.assignment_check.reader import reader_command
from mail_digest.assignment_check.report import item_lines, write_last_check
from mail_digest.assignment_check.visit import SiteVisit
from mail_digest.assignment_check.writer import (
    SITE_RULES,
    open_lines,
    select_items,
    writer_command,
    writer_context,
)
from mail_digest.claude import ClaudeNotFoundError, ClaudeRun, parse_result
from mail_digest.digest_email import DigestEmail, RunEdits, email_digest, run_changes
from mail_digest.kb import GuardReport, find_targets, is_reviewed
from mail_digest.memory import DigestState, load_state, save_state
from mail_digest.settings import MAX_ANNOUNCED_KEYS
from mail_digest.steps import EditJob, announce_once, email_alert, kb_alerts, run_guarded_edit

log = logging.getLogger(__name__)

# Used when no claude is found: its launch then fails, which stops the check.
MISSING_CLAUDE = Path("claude.exe")


@dataclass(frozen=True)
class CheckDeps:
    """Everything run_check uses from outside.

    visit(site, pages) runs one browser-tool-visit launch; read and write(argv,
    context) run the reader and writer claudes; notify(text) is True once the hub
    queued it; send_email(email) is True once the digest email was sent;
    refresh_board() never raises; is_reviewed(life_dir, path) is git's say on a
    flagged file.
    """

    life_dir: Path
    state_path: Path
    rejected_dir: Path
    last_check_path: Path
    config: CheckConfig
    visit: Callable[[str, tuple[Page, ...]], SiteVisit]
    read: Callable[[list[str], str], ClaudeRun]
    write: Callable[[list[str], str], ClaudeRun]
    notify: Callable[[str], bool]
    # No default, so a test can't send real mail by leaving it out.
    send_email: Callable[[DigestEmail], bool]
    refresh_board: Callable[[], None]
    now: Callable[[], datetime]
    find_claude: Callable[[], Path]
    is_reviewed: Callable[[Path, str], bool] = is_reviewed


@dataclass(frozen=True)
class CheckOutcome:
    """The exit code (0 success, 1 failure) and the lines the foreground CLI prints."""

    exit_code: int
    lines: tuple[str, ...] = ()


@dataclass(frozen=True)
class Written:
    """The writer step's result. edits is None when no writer ran."""

    is_ok: bool
    state: DigestState
    guard: GuardReport = field(default_factory=GuardReport)
    edits: RunEdits | None = None
    waiting: int = 0


def run_check(deps: CheckDeps) -> CheckOutcome:
    """One check (see the module docstring). A crash is logged and spoken, and is exit 1."""
    try:
        return _run(deps)
    except Exception:
        log.exception("assignment check crashed")
        deps.notify(CRASHED)
        return CheckOutcome(1, (CRASHED,))


def _run(deps: CheckDeps) -> CheckOutcome:
    """A real check. Raises on anything unexpected (run_check catches it)."""
    now = deps.now()
    run_start = int(now.timestamp())
    state = load_state(deps.state_path, MAX_ANNOUNCED_KEYS)
    claude = _find_claude(deps)
    gathered = gather(GatherDeps(deps.config, deps.visit, deps.read, reader_command(claude)), now)
    if gathered.stopped:
        notices = kb_alerts(GuardReport(), state, run_start, CHECK_NAME)
        _announce(deps, state, notices, run_start, gathered.stopped)
        return CheckOutcome(1, (gathered.stopped,))
    findings = check_findings(list(gathered.sites), now)
    write_last_check(deps.last_check_path, findings, now)
    written = _write(deps, state, findings, now, claude)
    notices = problem_notices(findings.problems, run_start)
    notices += kb_alerts(written.guard, written.state, run_start, CHECK_NAME)
    if not written.is_ok:
        _announce(deps, written.state, notices, run_start, stopped_line("the writer failed"))
        return CheckOutcome(1, tuple(item_lines(findings)))
    guard = written.guard
    if guard.reverted or guard.unexpected:
        log.warning("not speaking the items: the guard undid or found other edits")
    else:
        notices += item_notices(findings.items)
    # A check whose edit the guard undid may have been steered, so it sends no email.
    if written.edits and not guard.reverted and not email_digest(written.edits, deps.send_email):
        notices = [email_alert(run_start, CHECK_NAME), *notices]
    closing = done_line(_update_count(written.edits), written.waiting)
    _announce(deps, written.state, notices, run_start, closing)
    deps.refresh_board()
    return CheckOutcome(0, tuple(item_lines(findings)))


def _write(
    deps: CheckDeps, state: DigestState, findings: Findings, now: datetime, claude: Path
) -> Written:
    """Run the writer on this check's budget of items, under the guard (skipped if none)."""
    targets = find_targets(deps.life_dir, now.date())
    lines = open_lines({path: _text(deps.life_dir / path) for path in targets.editable})
    selection = select_items(findings.items, lines)
    if not (selection.changes or selection.adds):
        log.info("nothing for the writer this check; not starting it")
        return Written(is_ok=True, state=state, waiting=selection.spilled)
    argv = writer_command(claude, targets.editable)
    context = writer_context(now, targets, selection, findings.problems)
    job = EditJob(
        life_dir=deps.life_dir,
        state_path=deps.state_path,
        rejected_dir=deps.rejected_dir / f"{now:%Y%m%d-%H%M%S}-site",
        editable=targets.editable,
        is_reviewed=deps.is_reviewed,
        rules=SITE_RULES,
    )
    edit = run_guarded_edit(job, state, lambda: deps.write(argv, context))
    result = parse_result(edit.run, ())
    if result.denials:
        log.warning("the writer's refused tool calls: %r", list(result.denials))
    if result.is_success:
        log.info("writer done (cost %s USD); summary: %r", result.cost_usd, result.summary)
    else:
        log.error("the writer failed: %s", result.error)
    return Written(
        is_ok=result.is_success and not edit.guard.failed,
        state=replace(state, needs_review=edit.needs_review),
        guard=edit.guard,
        edits=RunEdits(deps.life_dir, now.date(), targets.editable, edit.before),
        waiting=selection.spilled,
    )


def _announce(
    deps: CheckDeps,
    state: DigestState,
    notices: list[Announcement],
    run_start: int,
    closing: str,
) -> None:
    """Speak the check's announcements once with its closing line, and save the state."""
    save_state(
        deps.state_path,
        announce_once(state, notices, deps.notify, run_start, closing, CHECK_NAME),
    )


def _update_count(edits: RunEdits | None) -> int:
    """How many lines the writer added or changed (after the guard), 0 if none ran."""
    if edits is None:
        return 0
    return sum(
        len(lines) for lines in run_changes(edits.life_dir, edits.before, edits.editable).values()
    )


def _find_claude(deps: CheckDeps) -> Path:
    """claude.exe, or MISSING_CLAUDE (logged), whose launch then fails the reader."""
    try:
        return deps.find_claude()
    except ClaudeNotFoundError as error:
        log.error("%s", error)
        return MISSING_CLAUDE


def _text(path: Path) -> str:
    """An editable file's text for the budget, "" if it can't be read (logged).

    The guarded edit snapshots it again, and stops before the writer if it can't.
    """
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError as error:
        log.warning("couldn't read %s for the budget: %s", path.name, error)
        return ""
