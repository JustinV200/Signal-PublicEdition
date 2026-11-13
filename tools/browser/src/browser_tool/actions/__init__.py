"""Public API of browser_tool.actions: one async function per MCP tool.

Each takes an ActionContext first and returns the text for the model, or raises
ActionError with a safe message. Playwright exceptions may also escape; callers
map them with describe_playwright_error and must never show their raw text.
"""

from browser_tool.actions.context import (
    NO_VAULT_PASSWORD_REFUSAL,
    PASSWORD_FIELD_REFUSAL,
    ActionContext,
    RefLabels,
)
from browser_tool.actions.dialogs import answer_dialog, dialog_notes
from browser_tool.actions.downloads import download_notes, read_download
from browser_tool.actions.errors import ActionError, describe_playwright_error
from browser_tool.actions.guards import FILLED_CREDENTIALS_MESSAGE, TAB_MOVED_REFUSAL
from browser_tool.actions.login import fill_login, list_credentials
from browser_tool.actions.navigation import (
    back,
    close_tab,
    forward,
    list_tabs,
    navigate,
    new_tab,
    reload,
    switch_tab,
)
from browser_tool.actions.page import find, screenshot, snapshot, wait_for
from browser_tool.actions.pointer import (
    click,
    click_at,
    drag,
    hover,
    press_key,
    scroll,
    select_option,
    type_text,
)
from browser_tool.actions.secret_scrub import TabReadError, scrub_secrets
from browser_tool.actions.signin import LOGIN_LOOP_REFUSAL, wait_for_duo
from browser_tool.actions.untrusted import UNTRUSTED_CLOSE, UNTRUSTED_OPEN
from browser_tool.actions.uploads import upload_file

__all__ = [
    "FILLED_CREDENTIALS_MESSAGE",
    "LOGIN_LOOP_REFUSAL",
    "NO_VAULT_PASSWORD_REFUSAL",
    "PASSWORD_FIELD_REFUSAL",
    "TAB_MOVED_REFUSAL",
    "UNTRUSTED_CLOSE",
    "UNTRUSTED_OPEN",
    "ActionContext",
    "ActionError",
    "RefLabels",
    "TabReadError",
    "answer_dialog",
    "back",
    "click",
    "click_at",
    "close_tab",
    "describe_playwright_error",
    "dialog_notes",
    "download_notes",
    "drag",
    "fill_login",
    "find",
    "forward",
    "hover",
    "list_credentials",
    "list_tabs",
    "navigate",
    "new_tab",
    "press_key",
    "read_download",
    "reload",
    "screenshot",
    "scroll",
    "scrub_secrets",
    "select_option",
    "snapshot",
    "switch_tab",
    "type_text",
    "upload_file",
    "wait_for",
    "wait_for_duo",
]
