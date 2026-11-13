"""Logs what a run found: its windows, the mail it gathered, and the validated result.

Everything the model wrote is logged with %r, so text shaped by an email can't
forge extra log lines.
"""

import logging

from mail_digest.claude import RunResult
from mail_digest.mailbox import GatheredMail
from mail_digest.memory import Window
from mail_digest.settings import CLAUDE_STDERR_PATH

log = logging.getLogger(__name__)


def log_windows(windows: dict[str, Window]) -> None:
    """Log the run's windows, and warn about mail the max lookback skipped."""
    log.info("run starting; windows %s", {a: (w.after, w.before) for a, w in windows.items()})
    for alias, window in windows.items():
        if window.skipped_since is not None:
            log.warning(
                "%s: mail between %d and %d is past the max lookback and won't be read",
                alias,
                window.skipped_since,
                window.after,
            )


def log_mail(mail: GatheredMail) -> None:
    """Log each searched account's message count and each account that wasn't searched."""
    log.info(
        "searched %s; messages %s",
        list(mail.completed),
        {alias: len(messages) for alias, messages in mail.messages.items()},
    )
    for problem in mail.problems:
        log.warning("account %s is %r and wasn't searched", problem.alias, problem.status)


def log_result(result: RunResult) -> None:
    """Log the run's outcome. Refused calls and suspicious mail are warnings."""
    log.info("claude %s", result.claude_version or "version unknown")
    if result.denials:
        log.warning("refused tool calls (check the mail for injection): %r", list(result.denials))
    if not result.is_success:
        log.error(
            "run failed: %s (cost %s USD; claude's stderr is in %s)",
            result.error,
            result.cost_usd,
            CLAUDE_STDERR_PATH,
        )
        return
    for email in result.suspicious:
        log.warning(
            "suspicious email, read it yourself: account %s, message %s, from %s",
            email.alias,
            email.message_id,
            email.sender,
        )
    if result.dropped:
        log.warning("dropped %d malformed or over-cap output entries", result.dropped)
    log.info("run done (cost %s USD); summary: %r", result.cost_usd, result.summary)
