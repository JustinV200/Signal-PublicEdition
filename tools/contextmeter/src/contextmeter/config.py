"""The tool's optional config file, contextmeter.toml (gitignored, copied from the example).

Its one key, `window_tokens`, sets the context window for every model; setup writes it
(`setup config contextmeter`). A missing file means "use the built-in table".
"""

import tomllib
from pathlib import Path

# parents: [0] contextmeter, [1] src, [2] tools/contextmeter
CONFIG_FILE = Path(__file__).resolve().parents[2] / "contextmeter.toml"


def configured_window(config_file: Path) -> int:
    """Return `window_tokens` from `config_file`, or 0 when unset, missing or not positive.

    Raises:
        tomllib.TOMLDecodeError: The file isn't valid TOML (the hook logs it).
        OSError: The file exists but can't be read.
    """
    if not config_file.exists():
        return 0
    with config_file.open("rb") as handle:
        value = tomllib.load(handle).get("window_tokens", 0)
    # bool is an int subclass, so rule it out explicitly.
    is_valid = isinstance(value, int) and not isinstance(value, bool) and value > 0
    return value if is_valid else 0
