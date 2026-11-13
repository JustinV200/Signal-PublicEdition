"""Public API of calendar_tool.auth: read-only scopes, sign-in and the stored token.

Nothing here returns or logs a token or the client secret.
"""

from calendar_tool.auth.session import SCOPES, load_client, open_session
from calendar_tool.auth.sign_in import sign_in
from calendar_tool.auth.token_file import StoredSignIn, load_sign_in, save_sign_in

__all__ = [
    "SCOPES",
    "StoredSignIn",
    "load_client",
    "load_sign_in",
    "open_session",
    "save_sign_in",
    "sign_in",
]
