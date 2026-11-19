"""CalendarError and its kinds: every failure the calendar tool expects and can explain.

Each message is safe to print: it never holds a token, the client secret or an
exception chain that might. The CLI prints them as one line and exits non-zero.
"""


class CalendarError(Exception):
    """Base for expected calendar-tool failures. str(error) is always safe to show."""


class SetupError(CalendarError):
    """The OAuth client file is missing or invalid, or nobody has signed in yet."""


class ReauthRequired(CalendarError):
    """The stored sign-in no longer works; the owner must run `calendar add` again."""

    def __init__(self, reason: str) -> None:
        """Args: reason: short, secret-free cause (e.g. "Google revoked the sign-in")."""
        super().__init__(f"{reason}. Re-run `calendar add`.")


class OfflineError(CalendarError):
    """Google couldn't be reached (network down, DNS, timeout)."""


class ApiError(CalendarError):
    """The Calendar API answered with an error or a body that isn't what it documents."""


class ChangeRefused(CalendarError):
    """A change wasn't made: the owner didn't click Allow, or the event can't take it."""
