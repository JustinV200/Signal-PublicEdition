"""Public API of mail_tool.service: the mail operations, sign-in, the send approval gate,
and the self-only send's fixed address."""

from mail_tool.service.factory import build_service
from mail_tool.service.mailbox import (
    DEFAULT_MAX_RESULTS,
    MAX_RESULTS_LIMIT,
    MailService,
    SessionOpener,
)
from mail_tool.service.self_send import SELF_ADDRESS
from mail_tool.service.send_gate import SendGate, confirm_text
from mail_tool.service.sign_in import AccountSignIn
from mail_tool.service.untrusted import CLOSE_TAG, OPEN_TAG, wrap_untrusted

__all__ = [
    "CLOSE_TAG",
    "DEFAULT_MAX_RESULTS",
    "MAX_RESULTS_LIMIT",
    "OPEN_TAG",
    "SELF_ADDRESS",
    "AccountSignIn",
    "MailService",
    "SendGate",
    "SessionOpener",
    "build_service",
    "confirm_text",
    "wrap_untrusted",
]
