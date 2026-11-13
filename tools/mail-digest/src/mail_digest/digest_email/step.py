"""The digest email step at the end of a run: find the run's new lines, build the email, send it.

digest/run.py and assignment_check/run.py call email_digest after a successful run
whose edits the guard didn't undo. It never raises, so the email can't fail the run;
the runner speaks an alert when it returns False.
"""

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from mail_digest.digest_email.build import DigestEmail, build_digest_email
from mail_digest.digest_email.changes import run_changes

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class RunEdits:
    """What one run may have changed in life/.

    today: the run's local date. editable: the run's editable paths. before: the
    snapshot taken before claude started (kb.snapshot).
    """

    life_dir: Path
    today: date
    editable: tuple[str, ...]
    before: dict[str, bytes]


def email_digest(edits: RunEdits, send: Callable[[DigestEmail], bool]) -> bool:
    """Build the run's digest email and send it once. True only once send(email) is True.

    Never raises: a file that can't be read (or any other error) is logged and is
    False, as is a send that fails (send logs its own reason).
    """
    try:
        changes = run_changes(edits.life_dir, edits.before, edits.editable)
        return send(build_digest_email(edits.life_dir, edits.today, changes))
    except Exception:
        # Anything at all, since the email must never fail the digest; the traceback is logged.
        log.exception("couldn't build or send the digest email")
        return False
