"""Settings and their TOML loader: the one tunable is `[send] confirm` (default true).

The file is optional. Unknown sections or keys are an error, so a typo such as
`confrim = false` can't silently leave a setting at a value the owner didn't mean.
"""

import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from mail_tool.config.paths import CONFIG_PATH
from mail_tool.errors import SetupError

_KNOWN_KEYS = {"send": {"confirm"}}


@dataclass(frozen=True)
class Settings:
    """Mail tool settings.

    Attributes:
        send_confirm: Ask the owner in an Allow/Deny dialog before sending a draft.
    """

    send_confirm: bool = True


def load_settings(path: Path = CONFIG_PATH) -> Settings:
    """Read settings from TOML, or return the defaults when the file doesn't exist.

    Args:
        path: The config file.

    Returns:
        The validated settings.

    Raises:
        SetupError: The file is unreadable, not TOML, or has an unknown or mistyped key.
    """
    if not path.is_file():
        return Settings()
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError) as error:
        raise SetupError(f"Can't read {path}: {error}") from error
    _check_keys(data, path)
    confirm = data.get("send", {}).get("confirm", True)
    if not isinstance(confirm, bool):
        raise SetupError(f"{path}: [send] confirm must be true or false")
    return Settings(send_confirm=confirm)


def _check_keys(data: dict[str, Any], path: Path) -> None:
    """Reject any section or key this tool doesn't know."""
    for section, table in data.items():
        if section not in _KNOWN_KEYS or not isinstance(table, dict):
            raise SetupError(f"{path}: unknown section [{section}]")
        unknown = set(table) - _KNOWN_KEYS[section]
        if unknown:
            raise SetupError(f"{path}: unknown key(s) in [{section}]: {', '.join(sorted(unknown))}")
