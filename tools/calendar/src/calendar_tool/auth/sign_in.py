"""sign_in: `calendar add` - browser sign-in for the calendar scopes, then save the refresh token.

The address Google actually signed in must match the expected one, so picking
the wrong account in Google's chooser saves nothing.
"""

from collections.abc import Callable, Sequence
from pathlib import Path

from google.auth.transport.requests import AuthorizedSession
from google.oauth2.credentials import Credentials
from signal_googleauth import SignInError, run_browser_flow

from calendar_tool.auth.scopes import SCOPES
from calendar_tool.auth.session import load_client
from calendar_tool.auth.token_file import StoredSignIn, save_sign_in
from calendar_tool.errors import CalendarError
from calendar_tool.google_api import CalendarClient, primary_calendar_email

SUCCESS_PAGE = "Signed in to the Signal calendar tool. You can close this tab."

# (client JSON path, scopes, login hint, success page) -> credentials with a refresh token.
FlowRunner = Callable[[Path, Sequence[str], str | None, str], Credentials]
# credentials -> the signed-in address.
EmailFetcher = Callable[[Credentials], str]


def fetch_signed_in_email(credentials: Credentials) -> str:
    """Ask the Calendar API which address these credentials belong to.

    Raises:
        CalendarError: The request failed or gave no address.
    """
    return primary_calendar_email(CalendarClient(AuthorizedSession(credentials)))


def sign_in(
    paths: tuple[Path, Path],
    expected_email: str,
    run_flow: FlowRunner = run_browser_flow,
    fetch_email: EmailFetcher = fetch_signed_in_email,
) -> str:
    """Sign in through the browser and save the token.

    Args:
        paths: (OAuth client JSON, token file).
        expected_email: The signed-in address must equal it (any case).
        run_flow, fetch_email: The browser flow and address lookup (tests pass fakes).

    Returns:
        The signed-in address.

    Raises:
        SetupError: The client file is missing or invalid.
        CalendarError: Cancelled or failed sign-in, or a different account signed in.
    """
    client_path, token_path = paths
    load_client(client_path)  # fail before opening a browser
    wanted = expected_email.strip()
    try:
        credentials = run_flow(client_path, SCOPES, wanted, SUCCESS_PAGE)
    except SignInError as error:
        raise CalendarError(str(error)) from None
    if not credentials.refresh_token:
        raise CalendarError("Google didn't return a refresh token; run `calendar add` again.")
    email = fetch_email(credentials)
    if email.lower() != wanted.lower():
        raise CalendarError(
            f"Signed in as {email}, not {wanted}, so nothing was saved. "
            f"Run it again and pick {wanted} in Google's account chooser."
        )
    save_sign_in(token_path, StoredSignIn(email, credentials.refresh_token, SCOPES))
    return email
