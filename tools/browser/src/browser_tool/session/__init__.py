"""Public API of browser_tool.session: launching Edge, tracking its tabs, sign-ins and dialogs."""

from browser_tool.session.browser_session import BrowserClosedError, BrowserSession
from browser_tool.session.debug_env import DEBUG_ENV_VARS, clear_debug_env
from browser_tool.session.dialogs import (
    STOPPED_BY_DIALOG,
    AlertNote,
    DialogWatch,
    FileChooserWatch,
    PendingDialog,
    act_until_dialog,
    read_until_dialog,
    run_unless_dialog,
)
from browser_tool.session.login_loop import LOOP_WINDOW_S, MAX_FILLS_PER_WINDOW, LoginLoopGuard
from browser_tool.session.request_guard import BlockedRequest, BlockLog, install_request_guard

__all__ = [
    "DEBUG_ENV_VARS",
    "LOOP_WINDOW_S",
    "MAX_FILLS_PER_WINDOW",
    "STOPPED_BY_DIALOG",
    "AlertNote",
    "BlockLog",
    "BlockedRequest",
    "BrowserClosedError",
    "BrowserSession",
    "DialogWatch",
    "FileChooserWatch",
    "LoginLoopGuard",
    "PendingDialog",
    "act_until_dialog",
    "clear_debug_env",
    "install_request_guard",
    "read_until_dialog",
    "run_unless_dialog",
]
