"""What one digest run announces, in order: the runner's alerts, then the due items.

The runner's own alerts and reminders go first, so the due and overdue items can't
push them into the "plus N more" summary. The due items are picked by code from the
plans (deadlines/), so they're spoken on a failed run too, unless the guard says the
plans may have been steered.
"""

import logging
from pathlib import Path

from mail_digest.announce import Announcement
from mail_digest.claude import RunResult
from mail_digest.deadlines import pick_announcements
from mail_digest.digest.plan import RunPlan
from mail_digest.kb import GuardReport
from mail_digest.memory import DigestState
from mail_digest.steps import failure_alert, gap_notices, kb_alerts, signin_reminders

log = logging.getLogger(__name__)


def is_success(result: RunResult, guard: GuardReport) -> bool:
    """True if claude's run succeeded and the guard checked every edit it made."""
    return result.is_success and not guard.failed


def run_notices(
    plan: RunPlan, result: RunResult, guard: GuardReport, state: DigestState
) -> list[Announcement]:
    """The runner's own announcement candidates. state is the one this run saves.

    A failed run gets the KB alerts and, every few failures, a failure alert. A
    successful one gets the KB alerts, sign-in and search reminders and gap notices.
    """
    notices = kb_alerts(guard, state, plan.run_start)
    if not is_success(result, guard):
        alert = failure_alert(state.failures, plan.run_start)
        return [*notices, alert] if alert else notices
    return [
        *notices,
        *signin_reminders(plan.mail.problems, plan.targets.week),
        *gap_notices(plan.windows),
    ]


def due_items(life_dir: Path, plan: RunPlan, guard: GuardReport) -> list[Announcement]:
    """The due and overdue items, picked from the plans as the run left them.

    None are spoken when the guard undid an edit, found other life/ files changed, or
    couldn't check an edit: the plans may then hold text an email steered in, and the
    guard's alerts say what happened.
    """
    if guard.reverted or guard.unexpected or guard.failed:
        log.warning("not speaking due items: the guard undid, found or couldn't check edits")
        return []
    items = pick_announcements(life_dir, plan.now)
    log.info("due and overdue items: %r", [item.key for item in items])
    return items
