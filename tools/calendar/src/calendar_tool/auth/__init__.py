"""Public API of calendar_tool.auth: the scopes, sign-in, the stored token and the client.

Nothing here returns or logs a token or the client secret.
"""

from calendar_tool.auth.scopes import LEGACY_SCOPES, SCOPES, WRITE_SCOPE
from calendar_tool.auth.session import load_client, open_client
from calendar_tool.auth.sign_in import sign_in
from calendar_tool.auth.token_file import StoredSignIn, load_sign_in, save_sign_in

__all__ = [
    "LEGACY_SCOPES",
    "SCOPES",
    "WRITE_SCOPE",
    "StoredSignIn",
    "load_client",
    "load_sign_in",
    "open_client",
    "save_sign_in",
    "sign_in",
]
