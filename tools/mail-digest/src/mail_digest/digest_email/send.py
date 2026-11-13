"""Mails a digest email to the owner through the mail tool's `mail send-self`.

send-self only ever sends from the owner's own address to that same address, so it
needs no Allow dialog (tools/mail/src/mail_tool/service/self_send.py). The body goes
through a file in .state/, overwritten each run, so the last email stays readable
there. The CLI exits 0 once Gmail took the message and 2 on any MailError (no
account for that address, a refused body, Gmail or network trouble).
"""

import logging

from mail_digest.child_env import run_hidden
from mail_digest.digest_email.build import DigestEmail
from mail_digest.settings import DIGEST_EMAIL_PATH, MAIL_PROJECT, MAIL_SEND_TIMEOUT_S

log = logging.getLogger(__name__)


def send_command(email: DigestEmail) -> list[str]:
    """The argv that sends email's subject and the body file.

    An argv list, so no shell parses it; `--subject=` keeps a subject that starts
    with "-" from being read as an option.
    """
    return [
        "uv", "run", "--project", str(MAIL_PROJECT), "--frozen", "--no-sync",
        "mail", "send-self",
        f"--subject={email.subject}",
        "--body-file", str(DIGEST_EMAIL_PATH),
    ]  # fmt: skip


def send_digest_email(email: DigestEmail) -> bool:
    """Send email once. True only if send-self exited 0. Never raises: failures are logged."""
    try:
        DIGEST_EMAIL_PATH.parent.mkdir(parents=True, exist_ok=True)
        DIGEST_EMAIL_PATH.write_text(email.body, encoding="utf-8", newline="\n")
    except OSError as error:
        log.warning("couldn't write the digest email's body to %s: %s", DIGEST_EMAIL_PATH, error)
        return False
    is_sent = run_hidden("mail send-self", send_command(email), MAIL_SEND_TIMEOUT_S)
    if is_sent:
        log.info("emailed the digest %r", email.subject)
    return is_sent
