"""AccountSignIn: `mail add` - sign an account in through the browser and save its refresh token.

When --email is given, the address Google actually signed in must match it,
so picking the wrong account in Google's chooser saves nothing.
"""

from collections.abc import Callable
from pathlib import Path

from google.auth.transport.requests import AuthorizedSession
from google.oauth2.credentials import Credentials

from mail_tool.auth import (
    AccountRecord,
    TokenStore,
    load_client_config,
    normalize_alias,
    run_browser_flow,
)
from mail_tool.errors import AccountError, GmailError
from mail_tool.gmail import GmailClient

# (client JSON path, login hint) -> credentials with a refresh token.
FlowRunner = Callable[[Path, str | None], Credentials]
# (credentials, alias) -> the signed-in address.
EmailFetcher = Callable[[Credentials, str], str]


def fetch_profile_email(credentials: Credentials, alias: str) -> str:
    """Ask Gmail which address these credentials belong to (users/me/profile).

    Raises:
        MailError: The request failed or the profile had no address.
    """
    profile = GmailClient(AuthorizedSession(credentials), alias).get("profile")
    email = profile.get("emailAddress")
    if not isinstance(email, str) or "@" not in email:
        raise GmailError("Gmail's profile had no email address.")
    return email


class AccountSignIn:
    """Runs the sign-in for `mail add` and stores the result."""

    def __init__(
        self,
        store: TokenStore,
        client_path: Path,
        run_flow: FlowRunner = run_browser_flow,
        fetch_email: EmailFetcher = fetch_profile_email,
    ) -> None:
        """Args: store: where accounts go; client_path: the OAuth client JSON;
        run_flow and fetch_email: the browser flow and profile lookup (tests pass fakes)."""
        self._store = store
        self._client_path = client_path
        self._run_flow = run_flow
        self._fetch_email = fetch_email

    def add(self, alias: str, expected_email: str | None = None) -> AccountRecord:
        """Sign in and save (or replace) the account `alias`.

        Args:
            alias: The short name to use (e.g. "personal").
            expected_email: If given, the signed-in address must equal it (any case).

        Returns:
            The saved record.

        Raises:
            SetupError: The OAuth client file is missing or invalid.
            AccountError: Bad alias, cancelled/failed sign-in, or a different account signed in.
            MailError: Gmail couldn't be asked for the address.
        """
        alias = normalize_alias(alias)
        wanted = expected_email.strip() if expected_email else None
        load_client_config(self._client_path)  # fail before opening a browser
        credentials = self._run_flow(self._client_path, wanted)
        if not credentials.refresh_token:
            raise AccountError("Google didn't return a refresh token; run `mail add` again.")
        email = self._fetch_email(credentials, alias)
        if wanted and email.lower() != wanted.lower():
            raise AccountError(
                f"Signed in as {email}, not {wanted}, so nothing was saved. "
                f"Run it again and pick {wanted} in Google's account chooser."
            )
        record = AccountRecord(alias, email, credentials.refresh_token)
        self._store.save(record)
        return record
