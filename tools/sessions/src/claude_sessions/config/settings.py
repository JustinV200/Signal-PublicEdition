"""Settings for every part of the sessions tool, with defaults and environment overrides.

All tunables live here: where repos are searched for, the daemon and voice-hub
addresses, the state folder and the approval timeout. `load_settings` reads
the `SESSIONS_*` environment variables and validates them, so a bad value
fails at startup with a clear message instead of deep inside a command.
"""

import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

from claude_sessions.config.paths import (
    DEFAULT_DAEMON_PORT,
    DEFAULT_HUB_TOKEN_FILE,
    DEFAULT_STATE_DIR,
)

LOOPBACK_HOST = "127.0.0.1"
DEFAULT_REPO_ROOTS = (Path(r"C:\src"),)
DEFAULT_MAX_DEPTH = 4
# The audiohub voice hub's kernel server (tools/audiohub, `[ipc]` port).
DEFAULT_HUB_PORT = 8765
DEFAULT_APPROVAL_TIMEOUT_S = 120.0

# Environment overrides. Roots are separated by os.pathsep (";" on Windows).
ENV_REPO_ROOTS = "SESSIONS_REPO_ROOTS"
ENV_MAX_DEPTH = "SESSIONS_MAX_DEPTH"
ENV_DAEMON_PORT = "SESSIONS_DAEMON_PORT"
ENV_HUB_PORT = "SESSIONS_HUB_PORT"
ENV_STATE_DIR = "SESSIONS_STATE_DIR"

MIN_PORT = 1
MAX_PORT = 65535
MAX_ALLOWED_DEPTH = 10


class SettingsError(ValueError):
    """An environment override has a value the tool can't use."""


@dataclass(frozen=True)
class Settings:
    """Everything the tool's components are configured with.

    Attributes:
        repo_roots: Folders searched for git repos.
        max_depth: How many folder levels below a root are searched (root = 0).
        daemon_host: Loopback address the daemon listens on.
        daemon_port: The daemon's TCP port.
        hub_host: Loopback address of the audiohub voice hub.
        hub_port: The voice hub's kernel port.
        hub_token_file: Where the voice hub publishes the token its kernel requires.
        state_dir: Folder for sessions.json and the daemon log.
        approval_timeout_s: How long an approval dialog waits before denying.
    """

    repo_roots: tuple[Path, ...] = DEFAULT_REPO_ROOTS
    max_depth: int = DEFAULT_MAX_DEPTH
    daemon_host: str = LOOPBACK_HOST
    daemon_port: int = DEFAULT_DAEMON_PORT
    hub_host: str = LOOPBACK_HOST
    hub_port: int = DEFAULT_HUB_PORT
    hub_token_file: Path = field(default=DEFAULT_HUB_TOKEN_FILE)
    state_dir: Path = field(default=DEFAULT_STATE_DIR)
    approval_timeout_s: float = DEFAULT_APPROVAL_TIMEOUT_S


def load_settings(environ: Mapping[str, str] | None = None) -> Settings:
    """Build Settings from the defaults plus any `SESSIONS_*` environment overrides.

    Args:
        environ: Environment to read (default: os.environ).

    Returns:
        The validated settings.

    Raises:
        SettingsError: An override is empty, not a number, or out of range.
    """
    env = os.environ if environ is None else environ
    defaults = Settings()
    return Settings(
        repo_roots=_roots(env.get(ENV_REPO_ROOTS), defaults.repo_roots),
        max_depth=_int(env, ENV_MAX_DEPTH, defaults.max_depth, 0, MAX_ALLOWED_DEPTH),
        daemon_port=_int(env, ENV_DAEMON_PORT, defaults.daemon_port, MIN_PORT, MAX_PORT),
        hub_port=_int(env, ENV_HUB_PORT, defaults.hub_port, MIN_PORT, MAX_PORT),
        state_dir=Path(env[ENV_STATE_DIR]) if env.get(ENV_STATE_DIR) else defaults.state_dir,
    )


def _roots(raw: str | None, default: tuple[Path, ...]) -> tuple[Path, ...]:
    """Parse an os.pathsep-separated root list, or return the default when unset."""
    if raw is None:
        return default
    roots = tuple(Path(part.strip()) for part in raw.split(os.pathsep) if part.strip())
    if not roots:
        raise SettingsError(f"{ENV_REPO_ROOTS} is set but names no folders")
    return roots


def _int(env: Mapping[str, str], name: str, default: int, low: int, high: int) -> int:
    """Read an integer override within [low, high], or return the default when unset."""
    raw = env.get(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError as error:
        raise SettingsError(f"{name} must be a whole number, got {raw!r}") from error
    if not low <= value <= high:
        raise SettingsError(f"{name} must be between {low} and {high}, got {value}")
    return value
