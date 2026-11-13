"""build_credentials: google-auth Credentials from a stored refresh token.

google-auth refreshes the access token before the first request and again
after a 401. Access tokens stay in memory only.
"""

from collections.abc import Sequence

from google.oauth2.credentials import Credentials

from signal_googleauth.client_config import ClientConfig


def build_credentials(
    refresh_token: str, client: ClientConfig, scopes: Sequence[str]
) -> Credentials:
    """Credentials with no access token yet; the first request refreshes them.

    Args:
        refresh_token: The account's stored refresh token.
        client: The OAuth client it was issued to.
        scopes: The scopes it was granted.

    Returns:
        google-auth Credentials.
    """
    return Credentials(
        token=None,
        refresh_token=refresh_token,
        token_uri=client.token_uri,
        client_id=client.client_id,
        client_secret=client.client_secret,
        scopes=list(scopes),
    )
