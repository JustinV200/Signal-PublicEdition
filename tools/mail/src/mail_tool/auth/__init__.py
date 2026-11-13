"""Public API of mail_tool.auth: the OAuth client file, encrypted token storage and sessions.

Nothing here returns or logs a token or client secret; records and configs
leave their secrets out of repr().
"""

from mail_tool.auth.browser_flow import run_browser_flow
from mail_tool.auth.client_secrets import ClientConfig, load_client_config
from mail_tool.auth.dpapi import DpapiError
from mail_tool.auth.sessions import SCOPES, GoogleSessions, build_credentials
from mail_tool.auth.token_store import AccountRecord, TokenStore, normalize_alias

__all__ = [
    "SCOPES",
    "AccountRecord",
    "ClientConfig",
    "DpapiError",
    "GoogleSessions",
    "TokenStore",
    "build_credentials",
    "load_client_config",
    "normalize_alias",
    "run_browser_flow",
]
