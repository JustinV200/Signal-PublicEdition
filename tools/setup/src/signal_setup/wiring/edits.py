"""Small file edits setup makes: a source constant, a .env key, the example .env.

The mail tool's SELF_ADDRESS and the calendar's OWNER_EMAIL are source constants on
purpose (no argument, env var or config can redirect a self-send), so setup writes the
user's address into them as one exact edit. Line endings are kept as they were.
"""

import re
import shutil
from pathlib import Path

# A loose address check: one @, no spaces, a dot in the domain. Google checks the rest.
EMAIL_PATTERN = re.compile(r"^[^@\s\"]+@[^@\s\"]+\.[^@\s\"]+$")
# .env values setup writes are single words or ';'-separated paths: nothing that needs quoting.
ENV_VALUE_PATTERN = re.compile(r"^[^\s\"'#=]+$")


def _read(path: Path) -> str:
    """The file's text with its line endings untouched."""
    with path.open(encoding="utf-8", newline="") as f:
        return f.read()


def _write(path: Path, text: str) -> None:
    """Write `text` without translating line endings."""
    with path.open("w", encoding="utf-8", newline="") as f:
        f.write(text)


def set_constant(path: Path, name: str, value: str) -> None:
    """Rewrite the module-level line `NAME = "..."` in `path` to hold `value`.

    Raises ValueError if `value` isn't an email address or the line isn't there exactly once.
    """
    if not EMAIL_PATTERN.match(value):
        raise ValueError(f"{value!r} doesn't look like an email address")
    pattern = re.compile(rf'^{re.escape(name)} = "[^"\r\n]*"', re.MULTILINE)
    text = _read(path)
    new_text, count = pattern.subn(f'{name} = "{value}"', text)
    if count != 1:
        raise ValueError(f'expected one `{name} = "..."` line in {path}, found {count}')
    _write(path, new_text)


def ensure_env_file(root: Path) -> Path:
    """Create .env from .env.example if it's missing (.mcp.json's servers load it)."""
    env = root / ".env"
    if not env.exists():
        shutil.copyfile(root / ".env.example", env)
    return env


def set_env_value(root: Path, key: str, value: str) -> None:
    """Set KEY=value in .env, replacing an existing KEY line. Raises ValueError on a bad value."""
    if not ENV_VALUE_PATTERN.match(value):
        raise ValueError("the value can't contain spaces, quotes, '#' or '='")
    env = ensure_env_file(root)
    lines = _read(env).splitlines()
    lines = [ln for ln in lines if not ln.startswith(f"{key}=")] + [f"{key}={value}"]
    _write(env, "\n".join(lines) + "\n")
