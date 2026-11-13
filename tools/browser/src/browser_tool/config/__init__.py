"""Public API of browser_tool.config: settings, the TOML loader and well-known paths."""

from browser_tool.config.confirm_categories import (
    ALL_CATEGORIES,
    CATEGORY_DELETE,
    CATEGORY_PATTERNS,
    CATEGORY_PURCHASE,
    CATEGORY_SEND,
    SIGN_IN_WORDING_RE,
)
from browser_tool.config.loader import ConfigError, load_settings, settings_from_dict
from browser_tool.config.paths import DEFAULT_CONFIG_PATH, TOOL_ROOT, resolve_tool_path
from browser_tool.config.settings import (
    BrowserSettings,
    DownloadSettings,
    DuoSettings,
    GateSettings,
    PolicySettings,
    Settings,
    UploadSettings,
    VisitSettings,
)

__all__ = [
    "ALL_CATEGORIES",
    "CATEGORY_DELETE",
    "CATEGORY_PATTERNS",
    "CATEGORY_PURCHASE",
    "CATEGORY_SEND",
    "SIGN_IN_WORDING_RE",
    "DEFAULT_CONFIG_PATH",
    "TOOL_ROOT",
    "BrowserSettings",
    "ConfigError",
    "DownloadSettings",
    "DuoSettings",
    "GateSettings",
    "PolicySettings",
    "Settings",
    "UploadSettings",
    "VisitSettings",
    "load_settings",
    "resolve_tool_path",
    "settings_from_dict",
]
