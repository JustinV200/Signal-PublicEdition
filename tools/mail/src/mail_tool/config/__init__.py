"""Public API of mail_tool.config: state paths and the optional TOML settings."""

from mail_tool.config.paths import (
    ACCOUNTS_DIR,
    CLIENT_SECRETS_PATH,
    CONFIG_PATH,
    REPO_ROOT,
    STATE_DIR,
    TOOL_ROOT,
)
from mail_tool.config.settings import Settings, load_settings

__all__ = [
    "ACCOUNTS_DIR",
    "CLIENT_SECRETS_PATH",
    "CONFIG_PATH",
    "REPO_ROOT",
    "STATE_DIR",
    "TOOL_ROOT",
    "Settings",
    "load_settings",
]
