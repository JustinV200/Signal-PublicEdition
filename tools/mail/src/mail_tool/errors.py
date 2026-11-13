"""MailError and its kinds: every failure the mail tool expects and can explain.

Each message is written for the owner or the model to act on, and never holds
a token, a client secret or an exception chain that might. The MCP layer turns
these into error results; the CLI prints them as one line.
"""


class MailError(Exception):
    """Base for expected mail-tool failures. str(error) is always safe to show."""


class SetupError(MailError):
    """The OAuth client JSON or the config file is missing or invalid."""


class AccountError(MailError):
    """An unknown or invalid account alias/address, or the wrong account signed in."""


class ReauthRequired(MailError):
    """The stored sign-in no longer works; the owner must run `mail add <alias>` again."""

    def __init__(self, alias: str, reason: str) -> None:
        """Build the message.

        Args:
            alias: The account alias to re-add.
            reason: Short, secret-free cause (e.g. "Google revoked the sign-in").
        """
        super().__init__(f"{reason}. Ask the owner to re-run `mail add {alias}`.")
        self.alias = alias


class OfflineError(MailError):
    """Google couldn't be reached (network down, DNS, timeout)."""


class GmailError(MailError):
    """The Gmail API answered with an error (not found, forbidden, bad query...)."""


class GmailNotFound(GmailError):
    """Gmail answered 404: the message, thread or draft doesn't exist (or was deleted)."""


class SendRefused(MailError):
    """The owner denied (or didn't answer) the send confirmation."""
