"""SCOPES and open_session: the read-only scopes, and an AuthorizedSession from the stored token.

google-auth refreshes the access token before the first request, in memory only.
"""

from pathlib import Path

import signal_googleauth
from google.auth.transport.requests import AuthorizedSession
from signal_googleauth import ClientConfig, ClientFileError, build_credentials

from calendar_tool.auth.token_file import load_sign_in
from calendar_tool.errors import SetupError

# Read-only on purpose: events and the calendar list, nothing that can create,
# edit or delete. The "Signal" calendar and its write scope are a later phase.
SCOPES = (
    "https://www.googleapis.com/auth/calendar.events.readonly",
    "https://www.googleapis.com/auth/calendar.calendarlist.readonly",
)


def load_client(client_path: Path) -> ClientConfig:
    """The shared OAuth client config, with failures as calendar SetupErrors.

    Raises:
        SetupError: The client file is missing or invalid.
    """
    try:
        return signal_googleauth.load_client_config(client_path)
    except ClientFileError as error:
        raise SetupError(str(error)) from None


def open_session(client_path: Path, token_path: Path) -> AuthorizedSession:
    """An AuthorizedSession for the stored sign-in.

    Args:
        client_path: The OAuth client JSON (the mail tool's).
        token_path: The DPAPI token file.

    Raises:
        SetupError: No client file or no sign-in yet.
        ReauthRequired: The token file can't be decrypted.
    """
    client = load_client(client_path)
    sign_in = load_sign_in(token_path)
    return AuthorizedSession(build_credentials(sign_in.refresh_token, client, SCOPES))
