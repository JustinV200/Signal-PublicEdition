"""run_browser_flow: the installed-app OAuth sign-in, in the owner's browser, for `mail add`.

Coding-rules note (section 7, local servers): the redirect listener is
google-auth-oauthlib's own one-shot server. It binds 127.0.0.1 on a random
port, serves exactly one request and exits. Instead of a token file, the OAuth
`state` value and a PKCE code verifier (both random per sign-in, checked by the
library) stop another local process or web page from completing the sign-in.
"""

from pathlib import Path

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow, WSGITimeoutError
from oauthlib.oauth2.rfc6749.errors import OAuth2Error

from mail_tool.auth.sessions import SCOPES
from mail_tool.errors import AccountError

LOOPBACK_HOST = "127.0.0.1"
ANY_FREE_PORT = 0
SIGN_IN_TIMEOUT_S = 300
SUCCESS_PAGE = "Signed in to the Signal mail tool. You can close this tab."


def run_browser_flow(client_path: Path, login_hint: str | None) -> Credentials:
    """Open Google's consent page and wait for the owner to approve.

    Args:
        client_path: The Desktop-app client JSON (already validated).
        login_hint: Pre-selects this address on Google's account chooser, if given.

    Returns:
        Credentials holding a refresh token.

    Raises:
        AccountError: Timed out, cancelled, or not every permission was granted.
    """
    flow = InstalledAppFlow.from_client_secrets_file(str(client_path), scopes=list(SCOPES))
    # prompt=consent makes Google issue a new refresh token even when re-adding an account.
    extra = {"prompt": "consent"}
    if login_hint:
        extra["login_hint"] = login_hint
    try:
        return flow.run_local_server(
            host=LOOPBACK_HOST,
            port=ANY_FREE_PORT,
            timeout_seconds=SIGN_IN_TIMEOUT_S,
            success_message=SUCCESS_PAGE,
            **extra,
        )
    # from None throughout: library errors here can carry the token response.
    except WSGITimeoutError:
        raise AccountError(f"No sign-in within {SIGN_IN_TIMEOUT_S} s; run it again.") from None
    except OAuth2Error as error:
        raise AccountError(f"Google sign-in failed ({error.error}).") from None
    except Warning:
        # oauthlib raises a bare Warning when Google granted fewer scopes than asked.
        raise AccountError(
            "Google granted only some permissions. Run it again and tick every box "
            "(read and compose)."
        ) from None
