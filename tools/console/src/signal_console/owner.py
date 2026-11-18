"""The owner's name in the console's words, from one key in the repo-root .env.

The chat marker (orchestrator/messages.py) and the `console tasks` help name the
owner. A name is per machine, so it lives in .env (gitignored) as
SIGNAL_OWNER_NAME, never in source. The console doesn't load .env (only the hub
and the whiteboard CLI get `--env-file`), so this reads that one key itself,
once per process. Stdlib only.
"""

from functools import cache
from pathlib import Path

OWNER_NAME_KEY = "SIGNAL_OWNER_NAME"
DEFAULT_OWNER_NAME = "the owner"
QUOTE = '"'


@cache
def read_owner_name(env_path: Path) -> str:
    """The SIGNAL_OWNER_NAME value in `env_path`, read once per path and process.

    One pair of surrounding double quotes is stripped (`KEY="First Last"`). The
    first line with the key wins.

    Args:
        env_path: The .env file (paths.ENV_FILE_PATH; tests pass a temp one).

    Returns:
        The name, or DEFAULT_OWNER_NAME when the file or the key is missing or
        the value is empty.

    Raises:
        OSError: The file exists but can't be read.
    """
    try:
        # utf-8-sig: a .env saved by Windows PowerShell may start with a BOM.
        text = env_path.read_text(encoding="utf-8-sig", errors="replace")
    except FileNotFoundError:
        return DEFAULT_OWNER_NAME
    for line in text.splitlines():
        key, has_value, value = line.partition("=")
        if has_value and key.strip() == OWNER_NAME_KEY:
            return _unquote(value.strip()) or DEFAULT_OWNER_NAME
    return DEFAULT_OWNER_NAME


def _unquote(value: str) -> str:
    """`value` without one pair of surrounding double quotes."""
    if len(value) >= 2 and value.startswith(QUOTE) and value.endswith(QUOTE):
        return value[1:-1].strip()
    return value
