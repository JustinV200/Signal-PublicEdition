"""Settings and their TOML loader: the one tunable is `[changes] confirm` (default true).

The file (.state/calendar.toml) is optional. Unknown sections or keys are an
error, so a typo such as `confrim = false` can't silently leave the gate at a
value the owner didn't mean. Same shape as tools/mail's `[send] confirm`.
"""

import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from calendar_tool.errors import SetupError

_KNOWN_KEYS = {"changes": {"confirm"}}


@dataclass(frozen=True)
class Settings:
    """Calendar tool settings.

    Attributes:
        changes_confirm: Ask the owner before changing, deleting or answering an event
            the tool didn't create. A whole-series change to such an event asks anyway.
    """

    changes_confirm: bool = True


def load_settings(path: Path) -> Settings:
    """Read settings from TOML, or return the defaults when the file doesn't exist.

    Args:
        path: The config file (usually paths.CONFIG_PATH).

    Raises:
        SetupError: The file is unreadable, not TOML, or has an unknown or mistyped key.
    """
    if not path.is_file():
        return Settings()
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError) as error:
        raise SetupError(f"Can't read {path.name}: {error}") from None
    _check_keys(data, path)
    confirm = data.get("changes", {}).get("confirm", True)
    if not isinstance(confirm, bool):
        raise SetupError(f"{path.name}: [changes] confirm must be true or false")
    return Settings(changes_confirm=confirm)


def _check_keys(data: dict[str, Any], path: Path) -> None:
    """Reject any section or key this tool doesn't know."""
    for section, table in data.items():
        if section not in _KNOWN_KEYS or not isinstance(table, dict):
            raise SetupError(f"{path.name}: unknown section [{section}]")
        unknown = set(table) - _KNOWN_KEYS[section]
        if unknown:
            raise SetupError(
                f"{path.name}: unknown key(s) in [{section}]: {', '.join(sorted(unknown))}"
            )
