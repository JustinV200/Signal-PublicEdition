"""Public API of whiteboard.config: settings dataclasses, the TOML loader, and paths.

Every other whiteboard package imports configuration from here only.
"""

from whiteboard.config.loader import load_settings, settings_from_dict
from whiteboard.config.paths import (
    AGENDA_FILE,
    CONSOLE_TASKS_FILE,
    DEFAULT_CONFIG_PATH,
    LIFE_DIR,
    REPO_ROOT,
    SLEEPMODE_STATE_FILE,
    STATE_DIR,
    TOOL_ROOT,
    USAGE_FILE,
)
from whiteboard.config.settings import (
    CAMERA_BACKENDS,
    AgentSettings,
    AlignSettings,
    CameraSettings,
    CaptureSettings,
    DisplaySettings,
    IdleSettings,
    Settings,
    WatcherSettings,
)
from whiteboard.config.validation import ConfigError

__all__ = [
    "AGENDA_FILE",
    "CAMERA_BACKENDS",
    "CONSOLE_TASKS_FILE",
    "DEFAULT_CONFIG_PATH",
    "LIFE_DIR",
    "REPO_ROOT",
    "SLEEPMODE_STATE_FILE",
    "STATE_DIR",
    "TOOL_ROOT",
    "USAGE_FILE",
    "AgentSettings",
    "AlignSettings",
    "CameraSettings",
    "CaptureSettings",
    "ConfigError",
    "DisplaySettings",
    "IdleSettings",
    "Settings",
    "WatcherSettings",
    "load_settings",
    "settings_from_dict",
]
