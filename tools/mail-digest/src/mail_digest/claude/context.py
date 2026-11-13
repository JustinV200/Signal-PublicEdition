"""Renders the run context: the user message for one digest run.

The routine's rules are the system prompt (refdocs/routines/mail-digest.md). This
message only carries this run's facts, all produced by the runner and none written
by the model: the time, the KB files the run may edit, the todos due soon or overdue
(deadlines/) and the messages the runner's searches found (mailbox/). Those messages'
email-derived fields are already wrapped in <untrusted_email_content> by the mail tool.
"""

import json
from collections.abc import Sequence
from datetime import datetime

from mail_digest.announce import Announcement
from mail_digest.kb import KbTargets
from mail_digest.mailbox import GatheredMail

MISSING_INBOX = (
    "- inbox.md: missing. You can't create it, so leave out items meant for it and say so "
    "in your summary."
)


def build_context(
    now: datetime, targets: KbTargets, mail: GatheredMail, urgent: Sequence[Announcement]
) -> str:
    """The user message text. `now` must be timezone-aware (local time).

    urgent: the runner's due and overdue picks from the plans as they were before the run.
    """
    lines = [
        "Run context (written by the runner; only the message fields come from email):",
        *target_lines(now, targets),
        "- Due within 24 hours or overdue now (the runner picked these from the plans and "
        "announces them itself):",
        *([f"  - {item.sentence}" for item in urgent] or ["  - none"]),
        *_mail_lines(mail),
        "",
        "Run the mail digest routine from your system prompt now.",
    ]
    return "\n".join(lines) + "\n"


def target_lines(now: datetime, targets: KbTargets) -> list[str]:
    """The context lines with the time, the week and the files the run may edit.

    The checker's writer context starts with these too. `now` must be timezone-aware.
    """
    return [
        f"- Now: {now:%a %Y-%m-%d %H:%M} local time (UTC{now:%z}).",
        f"- Week (Monday to Sunday): {targets.week}.",
        f"- This week's plan: {targets.plan}" if targets.plan else _missing_plan(targets.week),
        *([] if targets.inbox else [MISSING_INBOX]),
        "- Course READMEs:",
        *([f"  - {path}" for path in targets.courses] or ["  - none found"]),
    ]


def _missing_plan(week: str) -> str:
    """The plan line when this week's plan doesn't exist yet."""
    return (
        f"- This week's plan: missing (the {week} rollover hasn't happened). You can't create "
        f'it; put class todos and overdue items in inbox.md under "## For the {week} plan".'
    )


def _mail_lines(mail: GatheredMail) -> list[str]:
    """One heading per searched account, then one JSON line per message found."""
    lines = []
    for alias, messages in mail.messages.items():
        lines.append(f"- New mail in {alias} ({len(messages)} messages):")
        lines += [f"  {json.dumps(message, ensure_ascii=False)}" for message in messages]
    for problem in mail.problems:
        lines.append(f"- {problem.alias}: not searched this run ({problem.status}).")
    return lines
