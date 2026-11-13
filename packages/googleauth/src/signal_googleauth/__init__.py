"""Public API of signal_googleauth: Google OAuth plumbing shared by the mail and calendar tools.

The client file, the browser sign-in, credentials, DPAPI and the owner-only
atomic secret write. Nothing here returns or logs a token or client secret.
"""

from signal_googleauth.browser_flow import run_browser_flow
from signal_googleauth.client_config import ClientConfig, load_client_config
from signal_googleauth.credentials import build_credentials
from signal_googleauth.dpapi import DpapiError, protect, unprotect
from signal_googleauth.errors import ClientFileError, GoogleAuthError, SignInError
from signal_googleauth.secret_file import write_secret_atomically

__all__ = [
    "ClientConfig",
    "ClientFileError",
    "DpapiError",
    "GoogleAuthError",
    "SignInError",
    "build_credentials",
    "load_client_config",
    "protect",
    "run_browser_flow",
    "unprotect",
    "write_secret_atomically",
]
