"""Plans one digest run before claude starts: state, windows, mail, KB targets, context, argv.

Planning does routine step 2 in code: it searches the mail (mailbox/) and puts the
messages in the model's run context, with the due and overdue picks (deadlines/).
"""

import logging
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from mail_digest.claude import ClaudeNotFoundError, build_command, build_context, output_schema
from mail_digest.deadlines import pick_announcements
from mail_digest.digest.deps import RunDeps
from mail_digest.digest.report import log_mail, log_windows
from mail_digest.kb import KbTargets, find_targets
from mail_digest.mailbox import GatheredMail, gather_mail
from mail_digest.memory import DigestState, Lookback, Window, load_state, search_windows
from mail_digest.settings import (
    ACCOUNT_ALIASES,
    FIRST_RUN_LOOKBACK_S,
    MAX_ANNOUNCED_KEYS,
    MAX_LOOKBACK_S,
    SEARCH_OVERLAP_S,
)

log = logging.getLogger(__name__)

LOOKBACK = Lookback(FIRST_RUN_LOOKBACK_S, MAX_LOOKBACK_S, SEARCH_OVERLAP_S)
# Used when no claude is found: the launch then fails to start, which counts as a
# failed run, so the failure alert still fires.
MISSING_CLAUDE = Path("claude.exe")


@dataclass(frozen=True)
class RunPlan:
    """What the runner works out before starting claude."""

    stamp: str
    now: datetime
    run_start: int
    today: date
    state: DigestState
    windows: dict[str, Window]
    mail: GatheredMail
    targets: KbTargets
    context: str
    argv: list[str]


def plan_run(deps: RunDeps, dry_run: bool = False) -> RunPlan:
    """Load the state, search the mail and work out the KB targets, the context and the argv.

    A dry run writes nothing, not even the copy of a corrupt state file (it does
    search the mail, which only reads). Raises MailToolError if the mail tool can't
    list the accounts.
    """
    now = deps.now()
    run_start = int(now.timestamp())
    state = load_state(deps.state_path, MAX_ANNOUNCED_KEYS, keep_copy=not dry_run)
    windows = search_windows(state, ACCOUNT_ALIASES, run_start, LOOKBACK)
    log_windows(windows)
    mail = gather_mail(deps.mail, windows)
    log_mail(mail)
    targets = find_targets(deps.life_dir, now.date())
    urgent = pick_announcements(deps.life_dir, now)
    try:
        claude = deps.find_claude()
    except ClaudeNotFoundError as error:
        log.error("%s", error)
        claude = MISSING_CLAUDE
    argv = build_command(claude, output_schema(ACCOUNT_ALIASES), targets.editable)
    return RunPlan(
        stamp=f"{now:%Y%m%d-%H%M%S}",
        now=now,
        run_start=run_start,
        today=now.date(),
        state=state,
        windows=windows,
        mail=mail,
        targets=targets,
        context=build_context(now, targets, mail, urgent),
        argv=argv,
    )
