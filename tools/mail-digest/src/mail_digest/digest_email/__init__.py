"""mail_digest.digest_email: the email the owner gets after each run, built from life/ and sent
to the owner's own address through the mail tool's self-only send."""

from mail_digest.digest_email.build import DigestEmail, build_digest_email
from mail_digest.digest_email.changes import run_changes
from mail_digest.digest_email.send import send_digest_email
from mail_digest.digest_email.step import RunEdits, email_digest

__all__ = [
    "DigestEmail",
    "RunEdits",
    "build_digest_email",
    "email_digest",
    "run_changes",
    "send_digest_email",
]
