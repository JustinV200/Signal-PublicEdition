"""mail_digest.mailbox: routine step 2 in code, the account check and paged Gmail search."""

from mail_digest.mailbox.client import CliMailClient, MailClient, MailToolError
from mail_digest.mailbox.gather import SEARCH_FAILED, AccountProblem, GatheredMail, gather_mail

__all__ = [
    "SEARCH_FAILED",
    "AccountProblem",
    "CliMailClient",
    "GatheredMail",
    "MailClient",
    "MailToolError",
    "gather_mail",
]
