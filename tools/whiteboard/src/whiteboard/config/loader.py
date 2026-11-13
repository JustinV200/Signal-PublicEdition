"""Load `Settings` from an optional TOML file, falling back to the code defaults.

The file has one [table] per Settings section (display, camera, capture, ...).
Validation of each table is delegated to validation.build_section.
"""

import dataclasses
import tomllib
import typing
from pathlib import Path
from typing import Any

from whiteboard.config.paths import DEFAULT_CONFIG_PATH
from whiteboard.config.settings import Settings
from whiteboard.config.validation import ConfigError, build_section


def load_settings(path: Path | None = None) -> Settings:
    """Load settings from TOML, using defaults for anything the file leaves out.

    Args:
        path: The config file to read. When None, DEFAULT_CONFIG_PATH is read if it
            exists, and plain defaults are returned if it doesn't. An explicit path
            must exist.

    Returns:
        The validated, frozen Settings.

    Raises:
        ConfigError: If the file is missing (explicit path only), unreadable, not
            UTF-8, not valid TOML, or has an unknown section/key or a bad value.
    """
    if path is None:
        if not DEFAULT_CONFIG_PATH.is_file():
            return Settings()
        path = DEFAULT_CONFIG_PATH
    return settings_from_dict(_read_toml(path), source=str(path))


def settings_from_dict(data: dict[str, Any], source: str = "<settings>") -> Settings:
    """Validate an already-parsed config mapping and build Settings from it.

    Args:
        data: Mapping of section name to a table of key/value overrides.
        source: Where the data came from (usually a file path), for error messages.

    Returns:
        The validated Settings.

    Raises:
        ConfigError: On an unknown section, a non-table section, or a bad key/value.
    """
    section_classes = typing.get_type_hints(Settings)
    section_names = [field.name for field in dataclasses.fields(Settings)]
    unknown_sections = sorted(set(data) - set(section_names))
    if unknown_sections:
        raise ConfigError(
            f"{source}: unknown section(s): {', '.join(unknown_sections)}. "
            f"Valid sections: {', '.join(section_names)}"
        )

    sections: dict[str, Any] = {}
    for name, table in data.items():
        if not isinstance(table, dict):
            raise ConfigError(f"{source}: [{name}] must be a table, got {type(table).__name__}")
        try:
            sections[name] = build_section(section_classes[name], table, name)
        except ConfigError as error:
            raise ConfigError(f"{source}: {error}") from error
    return Settings(**sections)


def _read_toml(path: Path) -> dict[str, Any]:
    try:
        with path.open("rb") as config_file:
            return tomllib.load(config_file)
    except FileNotFoundError as error:
        raise ConfigError(f"config file not found: {path}") from error
    except tomllib.TOMLDecodeError as error:
        raise ConfigError(f"{path}: invalid TOML: {error}") from error
    except UnicodeDecodeError as error:
        raise ConfigError(f"{path}: not valid UTF-8 text: {error}") from error
    except OSError as error:
        raise ConfigError(f"cannot read config file {path}: {error}") from error
