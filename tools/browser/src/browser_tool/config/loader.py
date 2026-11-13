"""Load `Settings` from an optional TOML file, falling back to the code defaults.

The file has one [table] per Settings field (browser, policy, gates, duo,
downloads, uploads, visit). Each key is checked against the dataclass field's type;
unknown sections or keys are errors so typos don't silently fall back to defaults.

TODO: audiohub has a near-identical loader. Extract a shared config helper once a
repo-level shared Python package exists (tools must not import each other).
"""

import dataclasses
import ipaddress
import logging
import os
import re
import tomllib
import typing
from pathlib import Path
from typing import Any

from browser_tool.config.confirm_categories import ALL_CATEGORIES, RETIRED_CATEGORIES
from browser_tool.config.paths import DEFAULT_CONFIG_PATH, is_network_path, resolve_tool_path
from browser_tool.config.settings import DuoSettings, Settings, VisitSettings

logger = logging.getLogger(__name__)

MAX_PORT = 65535
# The saved cookies' folder name; actions.local_files refuses every path through one.
COOKIE_STATE_DIR = ".state"
# [duo] site_names: keys are exact hostnames as the browser reports them (no
# wildcard); values are short spoken names.
SITE_NAME_HOST_RE = re.compile(r"[a-z0-9-]+(\.[a-z0-9-]+)*")
SITE_NAME_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9 .-]{0,39}")


class ConfigError(ValueError):
    """The config file is missing (explicit path), unreadable, or has a bad value."""


def load_settings(path: Path | None = None) -> Settings:
    """Load settings from TOML, using defaults for anything the file leaves out.

    Args:
        path: The file to read. When None, DEFAULT_CONFIG_PATH is read if it exists,
            and plain defaults are returned if it doesn't. An explicit path must exist.

    Returns:
        The validated, frozen Settings.

    Raises:
        ConfigError: On a missing explicit file, invalid TOML, an unknown section or
            key, a wrong type, a non-positive number, an invalid regex pattern, an
            unknown [gates] always_confirm category, a voice hub address that
            isn't a loopback IP and port, a [duo] site_names entry that isn't an
            exact hostname with a short plain name, an [uploads] root or [downloads]
            folder on a network share or drive, or a [visit] login_host without its
            login_credential and login_from_hosts.
    """
    if path is None:
        if not DEFAULT_CONFIG_PATH.is_file():
            return Settings()
        path = DEFAULT_CONFIG_PATH
    return settings_from_dict(_read_toml(path), source=str(path))


def settings_from_dict(data: dict[str, Any], source: str = "<settings>") -> Settings:
    """Validate an already-parsed mapping of section -> table and build Settings.

    Args:
        data: Mapping of section name to a table of key/value overrides.
        source: Where the data came from, for error messages.

    Returns:
        The validated Settings.

    Raises:
        ConfigError: On an unknown section or key, or a bad value.
    """
    section_types = typing.get_type_hints(Settings)
    unknown = sorted(set(data) - set(section_types))
    if unknown:
        raise ConfigError(f"{source}: unknown section(s): {', '.join(unknown)}")
    sections = {}
    for name, table in data.items():
        if not isinstance(table, dict):
            raise ConfigError(f"{source}: [{name}] must be a table")
        sections[name] = _build_section(section_types[name], table, f"{source}: [{name}]")
    settings = _drop_retired_categories(Settings(**sections), source)
    _check_patterns_compile(settings.gates.patterns, source)
    _check_categories(settings.gates.always_confirm, source)
    _check_hub_address(settings.duo, source)
    _check_site_names(settings.duo, source)
    _check_local_folders(settings, source)
    _check_cookie_file(settings.browser.cookie_file, source)
    _check_visit_login(settings.visit, source)
    return settings


def _build_section(section_class: type, table: dict[str, Any], where: str) -> Any:
    field_types = typing.get_type_hints(section_class)
    unknown = sorted(set(table) - set(field_types))
    if unknown:
        raise ConfigError(f"{where} unknown key(s): {', '.join(unknown)}")
    values = {
        key: _coerce(value, field_types[key], f"{where} {key}") for key, value in table.items()
    }
    return dataclasses.replace(section_class(), **values)


def _coerce(value: Any, expected: Any, where: str) -> Any:
    """Check one value against its field type; converts lists to tuples, ints to floats."""
    if expected is bool:
        if not isinstance(value, bool):
            raise ConfigError(f"{where} must be true or false")
        return value
    if expected in (int, float):
        # bool is an int subclass in Python; reject it explicitly.
        is_number = isinstance(value, int | float) and not isinstance(value, bool)
        if not is_number or (expected is int and not isinstance(value, int)) or value <= 0:
            raise ConfigError(f"{where} must be a positive {expected.__name__}")
        return expected(value)
    if expected is str:
        if not isinstance(value, str) or not value:
            raise ConfigError(f"{where} must be a non-empty string")
        return value
    if typing.get_origin(expected) is dict:
        # The only dict field type is dict[str, str] ([duo] site_names).
        is_text_table = isinstance(value, dict) and all(
            isinstance(item, str) for pair in value.items() for item in pair
        )
        if not is_text_table:
            raise ConfigError(f"{where} must be a table of strings")
        return dict(value)
    # The only remaining field type is tuple[str, ...].
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ConfigError(f"{where} must be a list of strings")
    return tuple(value)


def _check_patterns_compile(patterns: tuple[str, ...], source: str) -> None:
    for pattern in patterns:
        try:
            re.compile(pattern)
        except re.error as error:
            raise ConfigError(f"{source}: [gates] bad pattern {pattern!r}: {error}") from error


def _drop_retired_categories(settings: Settings, source: str) -> Settings:
    """Drop retired [gates] always_confirm names, with one warning each.

    Older local config files still list them, and they should keep loading.
    """
    listed = settings.gates.always_confirm
    for name in sorted(set(listed) & set(RETIRED_CATEGORIES)):
        logger.warning("%s: [gates] always_confirm %r is retired and ignored", source, name)
    kept = tuple(name for name in listed if name not in RETIRED_CATEGORIES)
    if kept == listed:
        return settings
    gates = dataclasses.replace(settings.gates, always_confirm=kept)
    return dataclasses.replace(settings, gates=gates)


def _check_categories(categories: tuple[str, ...], source: str) -> None:
    """A misspelt category would silently stop asking, so it is an error."""
    unknown = sorted(set(categories) - set(ALL_CATEGORIES))
    if unknown:
        raise ConfigError(
            f"{source}: [gates] always_confirm has unknown categories {', '.join(unknown)}; "
            f"use any of {', '.join(ALL_CATEGORIES)}"
        )


def _check_hub_address(duo: DuoSettings, source: str) -> None:
    """The hub's token goes with every note, so it may only be sent to this machine."""
    if duo.hub_port > MAX_PORT:
        raise ConfigError(f"{source}: [duo] hub_port must be at most {MAX_PORT}")
    try:
        is_loopback = ipaddress.ip_address(duo.hub_host).is_loopback
    except ValueError:
        is_loopback = False
    if not is_loopback:
        raise ConfigError(f"{source}: [duo] hub_host must be a loopback IP such as 127.0.0.1")


def _check_site_names(duo: DuoSettings, source: str) -> None:
    """Names are spoken and shown to the model, so they stay short and plain."""
    for host, name in duo.site_names.items():
        if not SITE_NAME_HOST_RE.fullmatch(host):
            raise ConfigError(f"{source}: [duo] site_names key {host!r} must be an exact hostname")
        if not SITE_NAME_RE.fullmatch(name):
            raise ConfigError(
                f"{source}: [duo] site_names[{host!r}] must be letters, digits, spaces, "
                "dots and hyphens, at most 40 characters"
            )


def _check_local_folders(settings: Settings, source: str) -> None:
    """upload_file, read_download and the cookie store use these, so none may be on a network."""
    folders = [("[uploads] roots", root) for root in settings.uploads.roots]
    folders.append(("[downloads] folder", settings.downloads.folder))
    # Live cookies: a file on a share would also leak an NTLM handshake.
    folders.append(("[browser] cookie_file", settings.browser.cookie_file))
    for where, folder in folders:
        if is_network_path(resolve_tool_path(folder)):
            raise ConfigError(
                f"{source}: {where} {folder!r} is on a network share or drive; use a local folder"
            )


def _check_cookie_file(cookie_file: str, source: str) -> None:
    """The saved cookies must sit in a .state folder, which local file reads always refuse."""
    # normpath folds ".." first, so "a/.state/../x" can't pass on its lexical parents.
    folded = Path(os.path.normpath(resolve_tool_path(cookie_file)))
    parents = (part.lower() for part in folded.parent.parts)
    if COOKIE_STATE_DIR not in parents:
        raise ConfigError(
            f"{source}: [browser] cookie_file {cookie_file!r} must be inside a "
            f"{COOKIE_STATE_DIR} folder (upload_file and read_download never read those)"
        )


def _check_visit_login(visit: VisitSettings, source: str) -> None:
    """A login host needs the credential and the hosts it may be reached from.

    Without login_from_hosts no fill could pass the service check, so a config
    that sets only part of the login keys is a mistake, not a choice.
    """
    has_any = bool(visit.login_host or visit.login_credential or visit.login_from_hosts)
    has_all = bool(visit.login_host and visit.login_credential and visit.login_from_hosts)
    if has_any and not has_all:
        raise ConfigError(
            f"{source}: [visit] login_host, login_credential and login_from_hosts "
            "go together: set all three or none"
        )


def _read_toml(path: Path) -> dict[str, Any]:
    try:
        with path.open("rb") as config_file:
            return tomllib.load(config_file)
    except FileNotFoundError as error:
        raise ConfigError(f"config file not found: {path}") from error
    except tomllib.TOMLDecodeError as error:
        raise ConfigError(f"{path}: invalid TOML: {error}") from error
    except OSError as error:
        raise ConfigError(f"cannot read config file {path}: {error}") from error
