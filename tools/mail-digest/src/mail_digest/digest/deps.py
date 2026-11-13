"""The digest run's outside world (RunDeps), and the real one (default_deps).

run_once takes these as one value, so tests can run it with a fake mail tool,
claude, notify, mail sender, board, clock and git.
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from mail_digest.announce import send_notify
from mail_digest.claude import ClaudeRun, LaunchOptions, compose_prompt, find_claude, run_claude
from mail_digest.digest_email import DigestEmail, send_digest_email
from mail_digest.kb import is_reviewed
from mail_digest.mailbox import CliMailClient, MailClient
from mail_digest.settings import (
    CLAUDE_STDERR_PATH,
    DIGEST_PROMPT_PATH,
    LIFE_DIR,
    MAIL_TAG,
    PROMPT_PATH,
    REJECTED_DIR,
    RUN_TIMEOUT_S,
    STATE_PATH,
)
from mail_digest.steps import refresh_todo_board


@dataclass(frozen=True)
class RunDeps:
    """Everything run_once uses from outside: paths, the mail tool, claude, notify, the
    board, the clock, git.

    mail lists the accounts and searches them; launch(argv, context) runs claude;
    notify(text) returns True once the hub queued it; send_email(email) returns True
    once the owner's digest email was sent; refresh_board() updates the whiteboard's
    TODO view and never raises; is_reviewed(life_dir, path) says if a flagged file has
    been reviewed (git by default).
    """

    life_dir: Path
    state_path: Path
    rejected_dir: Path
    mail: MailClient
    launch: Callable[[list[str], str], ClaudeRun]
    notify: Callable[[str], bool]
    # No default, so a test can't send real mail by leaving it out.
    send_email: Callable[[DigestEmail], bool]
    refresh_board: Callable[[], None]
    now: Callable[[], datetime]
    find_claude: Callable[[], Path]
    is_reviewed: Callable[[Path, str], bool] = is_reviewed


def default_deps() -> RunDeps:
    """The real world: life/, the state file, claude.exe, audiohub, the mail tool, the
    whiteboard, the clock."""
    return RunDeps(
        life_dir=LIFE_DIR,
        state_path=STATE_PATH,
        rejected_dir=REJECTED_DIR,
        mail=CliMailClient(),
        launch=_launch,
        notify=send_notify,
        send_email=send_digest_email,
        refresh_board=refresh_todo_board,
        now=lambda: datetime.now().astimezone(),
        find_claude=find_claude,
    )


def _launch(argv: list[str], context: str) -> ClaudeRun:
    """Compose the routine's system prompt file, then run claude in life/.

    Raises OSError if the prompt can't be written or claude can't start (a failed run).
    """
    compose_prompt(PROMPT_PATH, MAIL_TAG, DIGEST_PROMPT_PATH)
    options = LaunchOptions(cwd=LIFE_DIR, timeout_s=RUN_TIMEOUT_S, stderr_path=CLAUDE_STDERR_PATH)
    return run_claude(argv, context, options)
