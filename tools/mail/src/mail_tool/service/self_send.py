"""The self-only send: one plain-text email to the owner's own address, with no Allow dialog.

Every other send goes through SendGate's dialog, because a draft's recipients come
from the model. This path skips it because nothing about the recipient comes from
input: To is SELF_ADDRESS, a constant, and the sending account is the saved account
whose email is that same address. So the mail can only go
from the owner's mailbox to itself. No argument, env var or config key can change
either, and a mail.toml key for one is refused like any unknown key (settings.py).

Only trusted code calls it: `mail send-self` (mail-digest's runner, after a run).
It isn't an MCP tool, so the model can't use it. The message is text/plain with no
attachments, and subject and body are checked here, before anything is sent.
"""

import unicodedata

from mail_tool.errors import MailError
from mail_tool.gmail import DraftContent, encode_draft

# The only address this path ever sends to, and the account it sends from.
# Setup (`setup mail`) writes your own address here; it is a constant on purpose.
SELF_ADDRESS = "owner.alt@example.com"
MAX_SUBJECT_CHARS = 200
# Far above a daily digest (a few KB), so only a runaway body hits it.
MAX_BODY_CHARS = 100_000
# The control characters a plain-text body needs. The subject may have none.
BODY_CONTROLS = frozenset("\n\t")
CONTROL_CATEGORY = "Cc"


def self_message(subject: str, body: str) -> str:
    """The base64url RFC 2822 message (Gmail's `raw`) of an email to SELF_ADDRESS.

    Nothing is escaped or stripped: text that breaks a rule is refused instead.

    Raises:
        MailError: The subject or body is too long or has a control character
            (the body may have line breaks and tabs).
    """
    if len(subject) > MAX_SUBJECT_CHARS:
        raise MailError(f"The subject is over {MAX_SUBJECT_CHARS} characters, so nothing was sent.")
    if len(body) > MAX_BODY_CHARS:
        raise MailError(f"The body is over {MAX_BODY_CHARS} characters, so nothing was sent.")
    if _has_control(subject, frozenset()) or _has_control(body, BODY_CONTROLS):
        raise MailError("The subject or body has a control character, so nothing was sent.")
    return encode_draft(DraftContent(to=SELF_ADDRESS, subject=subject, body=body))


def _has_control(text: str, allowed: frozenset[str]) -> bool:
    """True if text has a control character (category Cc) that isn't in allowed."""
    return any(
        unicodedata.category(char) == CONTROL_CATEGORY and char not in allowed for char in text
    )
