"""build_service: the real MailService, wired to the files in tools/mail/.state.

Shared by the CLI and the MCP server so both read the same accounts, client
file and settings.
"""

from mail_tool.auth import GoogleSessions, TokenStore
from mail_tool.config import ACCOUNTS_DIR, CLIENT_SECRETS_PATH, load_settings
from mail_tool.service.mailbox import MailService
from mail_tool.service.send_gate import SendGate


def build_service() -> MailService:
    """Create the production service. The client file is read lazily, on the first Gmail call.

    Raises:
        SetupError: .state/mail.toml exists but is invalid.
    """
    settings = load_settings()
    return MailService(
        TokenStore(ACCOUNTS_DIR),
        GoogleSessions(CLIENT_SECRETS_PATH),
        SendGate(settings.send_confirm),
    )
