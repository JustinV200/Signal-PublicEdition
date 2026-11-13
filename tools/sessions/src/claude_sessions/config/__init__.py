"""Public API of claude_sessions.config: settings and the tool's fixed file locations."""

from claude_sessions.config.paths import (
    REPO_ROOT,
    TOOL_ROOT,
    daemon_log_file,
    daemon_token_file,
    sessions_file,
)
from claude_sessions.config.settings import (
    DEFAULT_APPROVAL_TIMEOUT_S,
    LOOPBACK_HOST,
    Settings,
    SettingsError,
    load_settings,
)

__all__ = [
    "DEFAULT_APPROVAL_TIMEOUT_S",
    "LOOPBACK_HOST",
    "REPO_ROOT",
    "TOOL_ROOT",
    "Settings",
    "SettingsError",
    "daemon_log_file",
    "daemon_token_file",
    "load_settings",
    "sessions_file",
]
