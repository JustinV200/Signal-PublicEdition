"""run_browser_flow: the installed-app OAuth sign-in in the owner's default browser.

Used by `mail add` and `calendar add`. Coding-rules note (section 7, local
servers): the redirect listener is google-auth-oauthlib's own one-shot server.
It binds 127.0.0.1 on a random port, serves exactly one request and exits.
Instead of a token file, the OAuth `state` value and a PKCE code verifier (both
random per sign-in, checked by the library) stop another local process or web
page from completing the sign-in.
"""

from collections.abc import Sequence
from pathlib import Path

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow, WSGITimeoutError
from oauthlib.oauth2.rfc6749.errors import OAuth2Error

from signal_googleauth.errors import SignInError

LOOPBACK_HOST = "127.0.0.1"
ANY_FREE_PORT = 0
SIGN_IN_TIMEOUT_S = 300


def run_browser_flow(
    client_path: Path, scopes: Sequence[str], login_hint: str | None, success_message: str
) -> Credentials:
    """Open Google's consent page and wait for the owner to approve.

    Args:
        client_path: The Desktop-app client JSON (already validated).
        scopes: The OAuth scopes to ask for; all must be granted.
        login_hint: Pre-selects this address on Google's account chooser, if given.
        success_message: Shown in the browser tab once the sign-in is done.

    Returns:
        Credentials holding a refresh token.

    Raises:
        SignInError: Timed out, cancelled, or not every permission was granted.
    """
    flow = InstalledAppFlow.from_client_secrets_file(str(client_path), scopes=list(scopes))
    # prompt=consent makes Google issue a new refresh token even when signing in again.
    extra = {"prompt": "consent"}
    if login_hint:
        extra["login_hint"] = login_hint
    try:
        return flow.run_local_server(
            host=LOOPBACK_HOST,
            port=ANY_FREE_PORT,
            timeout_seconds=SIGN_IN_TIMEOUT_S,
            success_message=success_message,
            **extra,
        )
    # from None throughout: library errors here can carry the token response.
    except WSGITimeoutError:
        raise SignInError(f"No sign-in within {SIGN_IN_TIMEOUT_S} s; run it again.") from None
    except OAuth2Error as error:
        raise SignInError(f"Google sign-in failed ({error.error}).") from None
    except Warning:
        # oauthlib raises a bare Warning when Google granted fewer scopes than asked.
        raise SignInError(
            "Google granted only some permissions. Run it again and tick every box."
        ) from None
