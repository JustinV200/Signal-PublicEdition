"""GoogleSessions: turns a stored account into an AuthorizedSession that refreshes itself.

google-auth refreshes the access token before the first request and again
after a 401. Access tokens stay in memory only, cached per account for the
life of the process, so the MCP server doesn't refresh on every call.
"""

import threading
from pathlib import Path

from google.auth.transport.requests import AuthorizedSession
from google.oauth2.credentials import Credentials

from mail_tool.auth.client_secrets import ClientConfig, load_client_config
from mail_tool.auth.token_store import AccountRecord

# Read mail, and create/send drafts. gmail.compose doesn't allow deleting mail or changing labels.
SCOPES = (
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.compose",
)


def build_credentials(refresh_token: str, client: ClientConfig) -> Credentials:
    """Credentials with no access token yet; the first request refreshes them.

    Args:
        refresh_token: The account's stored refresh token.
        client: The OAuth client it was issued to.

    Returns:
        google-auth Credentials.
    """
    return Credentials(
        token=None,
        refresh_token=refresh_token,
        token_uri=client.token_uri,
        client_id=client.client_id,
        client_secret=client.client_secret,
        scopes=list(SCOPES),
    )


class GoogleSessions:
    """Opens (and caches) one AuthorizedSession per account. Safe to call from any thread."""

    def __init__(self, client_path: Path) -> None:
        """Args: client_path: The OAuth client JSON, read on first use."""
        self._client_path = client_path
        self._lock = threading.Lock()
        self._cache: dict[str, tuple[str, AuthorizedSession]] = {}

    def __call__(self, record: AccountRecord) -> AuthorizedSession:
        """Return the session for `record`, making a new one if its refresh token changed.

        Raises:
            SetupError: The OAuth client file is missing or invalid.
        """
        with self._lock:
            cached = self._cache.get(record.alias)
            if cached and cached[0] == record.refresh_token:
                return cached[1]
            client = load_client_config(self._client_path)
            session = AuthorizedSession(build_credentials(record.refresh_token, client))
            self._cache[record.alias] = (record.refresh_token, session)
            return session
