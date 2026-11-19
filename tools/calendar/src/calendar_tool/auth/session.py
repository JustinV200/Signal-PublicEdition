"""open_client: a CalendarClient over the stored sign-in; it writes only with the write scope.

google-auth refreshes the access token before the first request, in memory only.
The refresh asks for exactly the scopes the sign-in was granted, so an older
read-only sign-in keeps reading (asking for more would fail the refresh).
"""

from pathlib import Path

import signal_googleauth
from google.auth.transport.requests import AuthorizedSession
from signal_googleauth import ClientConfig, ClientFileError, build_credentials

from calendar_tool.auth.scopes import WRITE_SCOPE
from calendar_tool.auth.token_file import load_sign_in
from calendar_tool.errors import SetupError
from calendar_tool.google_api import CalendarClient


def load_client(client_path: Path) -> ClientConfig:
    """The shared OAuth client config, with failures as calendar SetupErrors.

    Raises:
        SetupError: The client file is missing or invalid.
    """
    try:
        return signal_googleauth.load_client_config(client_path)
    except ClientFileError as error:
        raise SetupError(str(error)) from None


def open_client(client_path: Path, token_path: Path) -> CalendarClient:
    """A CalendarClient for the stored sign-in; it refuses writes without WRITE_SCOPE.

    Args:
        client_path: The OAuth client JSON (the mail tool's).
        token_path: The DPAPI token file.

    Raises:
        SetupError: No client file or no sign-in yet.
        ReauthRequired: The token file can't be decrypted.
    """
    client = load_client(client_path)
    sign_in = load_sign_in(token_path)
    credentials = build_credentials(sign_in.refresh_token, client, sign_in.scopes)
    return CalendarClient(AuthorizedSession(credentials), can_write=WRITE_SCOPE in sign_in.scopes)
