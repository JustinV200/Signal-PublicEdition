"""sleepmode.toml: the optional per-machine config, its [lighting] and [input] sections.

The file is gitignored (sleepmode.example.toml is the template). [lighting] is read on
every sleep and wake, so an edit applies without restarting the MCP server; [input] is
read by each new keeper, so an edit applies from the next sleep. Every key is optional;
an unknown key or a wrong type is a ConfigError, which the lighting step turns into a
note and the keeper into a logged warning, instead of guessing what was meant.
"""

import math
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sleepmode.config.paths import CONFIG_FILE

_SECTIONS = {"lighting", "input"}
_LIGHTING_KEYS = {"enabled", "openrgb_path", "off_commands", "restore_commands"}
_INPUT_KEYS = {"mouse_move_px", "mouse_move_window_s"}


class ConfigError(ValueError):
    """sleepmode.toml can't be read or doesn't fit the expected shape."""


@dataclass(frozen=True)
class LightingSettings:
    """The [lighting] section.

    Attributes:
        enabled: False leaves every light alone at sleep and wake.
        openrgb_path: OpenRGB.exe; "" means the portable install under %LOCALAPPDATA%.
        off_commands: Vendor commands run at sleep, each an argv list (no shell).
        restore_commands: Vendor commands run at wake, the same way.
    """

    enabled: bool = True
    openrgb_path: str = ""
    off_commands: tuple[tuple[str, ...], ...] = ()
    restore_commands: tuple[tuple[str, ...], ...] = ()


@dataclass(frozen=True)
class InputSettings:
    """The [input] section: how far the mouse must move to wake sleep mode.

    Optical mice jitter by a few pixels on their own, so a move only wakes once the
    cursor spans mouse_move_px (across or down) within mouse_move_window_s. A deliberate
    nudge or shake covers that in a fraction of a second. Keys, clicks and the wheel
    still wake at once.

    Attributes:
        mouse_move_px: Pixels the cursor must span, horizontally or vertically.
        mouse_move_window_s: Seconds that span must happen within.
    """

    mouse_move_px: float = 100.0
    mouse_move_window_s: float = 1.5


def load_lighting_settings(path: Path = CONFIG_FILE) -> LightingSettings:
    """Read [lighting] from sleepmode.toml.

    Args:
        path: The config file; a missing file means every default.

    Raises:
        ConfigError: The file can't be read or parsed, or [lighting] has an unknown
            key or a value of the wrong type.
    """
    return _parse_lighting(_read_section(path, "lighting"), path.name)


def load_input_settings(path: Path = CONFIG_FILE) -> InputSettings:
    """Read [input] from sleepmode.toml.

    Args:
        path: The config file; a missing file means every default.

    Raises:
        ConfigError: The file can't be read or parsed, or [input] has an unknown key or
            a value that isn't a positive number.
    """
    section = _read_section(path, "input")
    unknown = set(section) - _INPUT_KEYS
    if unknown:
        raise ConfigError(f"{path.name}: unknown [input] key(s) {sorted(unknown)}")
    values = {key: _positive_number(section, key, path.name) for key in section}
    return InputSettings(**values)


def _read_section(path: Path, name: str) -> dict[str, Any]:
    """One section of the file as a dict; {} when the file or the section is missing."""
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError) as error:
        raise ConfigError(f"can't read {path.name}: {error}") from error
    unknown = set(data) - _SECTIONS
    if unknown:
        raise ConfigError(f"{path.name}: unknown section(s) {sorted(unknown)}")
    section = data.get(name, {})
    if not isinstance(section, dict):
        raise ConfigError(f"{path.name}: [{name}] isn't a table")
    return section


def _positive_number(section: dict[str, Any], key: str, name: str) -> float:
    value = section[key]
    # bool is an int in Python, so it's ruled out by name. TOML allows nan and inf: nan
    # would never compare as reached (no mouse wake) and inf would keep every point.
    is_number = isinstance(value, int | float) and not isinstance(value, bool)
    if not is_number or not math.isfinite(value) or value <= 0:
        raise ConfigError(f"{name}: [input] {key} must be a positive, finite number")
    return float(value)


def _parse_lighting(section: dict[str, Any], name: str) -> LightingSettings:
    unknown = set(section) - _LIGHTING_KEYS
    if unknown:
        raise ConfigError(f"{name}: unknown [lighting] key(s) {sorted(unknown)}")
    enabled = section.get("enabled", True)
    openrgb_path = section.get("openrgb_path", "")
    if not isinstance(enabled, bool):
        raise ConfigError(f"{name}: [lighting] enabled isn't true or false")
    if not isinstance(openrgb_path, str):
        raise ConfigError(f"{name}: [lighting] openrgb_path isn't a string")
    return LightingSettings(
        enabled=enabled,
        openrgb_path=openrgb_path,
        off_commands=_parse_commands(section, "off_commands", name),
        restore_commands=_parse_commands(section, "restore_commands", name),
    )


def _parse_commands(section: dict[str, Any], key: str, name: str) -> tuple[tuple[str, ...], ...]:
    """A list of argv lists, each a non-empty list of strings (run without a shell)."""
    commands = section.get(key, [])
    is_valid = isinstance(commands, list) and all(
        isinstance(argv, list) and argv and all(isinstance(arg, str) for arg in argv)
        for argv in commands
    )
    if not is_valid:
        raise ConfigError(f"{name}: [lighting] {key} must be a list of argv lists of strings")
    return tuple(tuple(argv) for argv in commands)
