"""Public API of audiohub.config: settings dataclasses, the TOML loader, and paths.

Every other audiohub package imports configuration from here only.
"""

from audiohub.config.brain_choice import with_brain_choice
from audiohub.config.loader import load_settings
from audiohub.config.paths import (
    BRAIN_CHOICE_PATH,
    CACHE_DIR,
    DEFAULT_CONFIG_PATH,
    MODELS_DIR,
    ORCHESTRATOR_CLAIM_PATH,
    REPO_ROOT,
    TOOL_ROOT,
)
from audiohub.config.settings import (
    MUSIC_BACKENDS,
    AudioSettings,
    BrainSettings,
    DuckingSettings,
    IpcSettings,
    KernelSettings,
    MusicSettings,
    PhoneSettings,
    Settings,
    SttSettings,
    TtsSettings,
    VadSettings,
    WakeSettings,
)
from audiohub.config.validation import ConfigError

__all__ = [
    "BRAIN_CHOICE_PATH",
    "CACHE_DIR",
    "DEFAULT_CONFIG_PATH",
    "MODELS_DIR",
    "MUSIC_BACKENDS",
    "ORCHESTRATOR_CLAIM_PATH",
    "REPO_ROOT",
    "TOOL_ROOT",
    "AudioSettings",
    "BrainSettings",
    "ConfigError",
    "DuckingSettings",
    "IpcSettings",
    "KernelSettings",
    "MusicSettings",
    "PhoneSettings",
    "Settings",
    "SttSettings",
    "TtsSettings",
    "VadSettings",
    "WakeSettings",
    "load_settings",
    "with_brain_choice",
]
