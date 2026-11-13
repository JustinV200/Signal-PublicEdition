"""The runner's own announcement candidates: alerts and reminders the model doesn't make.

- A reset alert on the run that found the state file corrupt and started fresh:
  any files it had flagged for review are forgotten, so the owner checks git.
- A review alert counting the files with an edit the KB guard couldn't check (their
  paths go to the log), on the run it failed and every run after until reviewed.
- A guard alert when the KB guard undid an edit, and another when files it doesn't
  guard changed during the run (it leaves those alone).
- A failure alert every FAILURE_ALERT_EVERY consecutive failed runs.
- An email alert on a successful run whose digest email couldn't be built or sent.
- A sign-in reminder for each account that needs re-auth or errors, and a search
  reminder for each whose search failed, keyed by week so they repeat at most
  weekly. Offline accounts are only logged: they come back by themselves and are
  retried next run.
- A skipped-mail notice once per gap the max lookback cut out of a window.
"""

import logging

from mail_digest.announce import Announcement
from mail_digest.kb import GuardReport
from mail_digest.mailbox import SEARCH_FAILED, AccountProblem
from mail_digest.memory import DigestState, Window
from mail_digest.settings import FAILURE_ALERT_EVERY, MAX_LOOKBACK_S

log = logging.getLogger(__name__)

DAY_S = 24 * 3600
# The runner's name in the alerts kb_alerts makes.
DIGEST_NAME = "mail digest"
# Per account status: the reminder's key kind and its sentence.
ACCOUNT_REMINDERS = {
    "needs re-auth": ("signin", "The {alias} mail account needs signing in again."),
    "error": ("signin", "The {alias} mail account has an error. Try signing it in again."),
    SEARCH_FAILED: (
        "search",
        "The mail digest couldn't search the {alias} account. Check its log.",
    ),
}


def kb_alerts(
    guard: GuardReport, state: DigestState, run_start: int, name: str = DIGEST_NAME
) -> list[Announcement]:
    """The alerts about life/, in order: a state reset, files to review, undone edits,
    other changes.

    state: the one this run saves (its needs_review is the files flagged after it).
    name: the runner, as spoken ("mail digest", "assignment check").
    """
    alerts = [_reset_alert(run_start, name)] if state.was_reset else []
    if state.needs_review:
        alerts.append(_review_alert(state.needs_review, run_start, name))
    if guard.reverted:
        alerts.append(_guard_alert(guard.reverted, run_start, name))
    if guard.unexpected:
        alerts.append(_unexpected_alert(guard.unexpected, run_start, name))
    return alerts


def _reset_alert(run_start: int, name: str) -> Announcement:
    """The alert for a corrupt state file this run replaced with a fresh one."""
    return Announcement(
        f"reset|{run_start}",
        f"The {name}'s state file was corrupt and has been reset, so files it had "
        "flagged for review are forgotten. Check git diff life.",
    )


def _review_alert(paths: tuple[str, ...], run_start: int, name: str) -> Announcement:
    """The alert for life/ files whose edit the KB guard couldn't check.

    Keyed by run, so it's spoken every run while the files are flagged. Only the
    count is spoken (long paths are tiring to hear); the paths are logged.
    """
    log.warning("files to review (the guard couldn't check them): %r", list(paths))
    files = "1 life file" if len(paths) == 1 else f"{len(paths)} life files"
    return Announcement(
        f"review|{run_start}",
        f"The {name} couldn't check its edits to {files}. "
        "Check git diff life, then commit or revert.",
    )


def _guard_alert(reverted: tuple[str, ...], run_start: int, name: str) -> Announcement:
    """The alert for edits the KB guard undid this run."""
    files = "file" if len(reverted) == 1 else "files"
    return Announcement(
        f"guard|{run_start}",
        f"The {name} undid its edit to {len(reverted)} life {files}. Check its log.",
    )


def _unexpected_alert(unexpected: tuple[str, ...], run_start: int, name: str) -> Announcement:
    """The alert for other life/ files that changed during the run (left alone)."""
    files = "file" if len(unexpected) == 1 else "files"
    return Announcement(
        f"unexpected|{run_start}",
        f"{len(unexpected)} other life {files} changed while the {name} ran. "
        "It left them alone. Check its log.",
    )


def email_alert(run_start: int, name: str = DIGEST_NAME) -> Announcement:
    """The alert for a digest email that couldn't be built or sent this run (never retried)."""
    return Announcement(
        f"email|{run_start}",
        f"The {name} couldn't email you today's digest. Check its log.",
    )


def failure_alert(failures: int, run_start: int) -> Announcement | None:
    """The alert after every FAILURE_ALERT_EVERY consecutive failures, else None."""
    if failures == 0 or failures % FAILURE_ALERT_EVERY:
        return None
    return Announcement(
        f"failure|{run_start}",
        f"The mail digest has failed {failures} runs in a row. Check its log.",
    )


def signin_reminders(problems: tuple[AccountProblem, ...], week: str) -> list[Announcement]:
    """One reminder per account that needs signing in again or whose search failed, keyed
    per week (its folder name)."""
    reminders = []
    for problem in problems:
        if problem.status in ACCOUNT_REMINDERS:
            kind, sentence = ACCOUNT_REMINDERS[problem.status]
            key = f"{kind}|{problem.alias}|{week.lower()}"
            reminders.append(Announcement(key, sentence.format(alias=problem.alias)))
    return reminders


def gap_notices(windows: dict[str, Window]) -> list[Announcement]:
    """One notice per account whose window the max lookback cut short."""
    days = MAX_LOOKBACK_S // DAY_S
    return [
        Announcement(
            f"gap|{alias}|{window.skipped_since}",
            f"The mail digest skipped {alias} mail older than {days} days. "
            "Check that inbox by hand.",
        )
        for alias, window in windows.items()
        if window.skipped_since is not None
    ]
