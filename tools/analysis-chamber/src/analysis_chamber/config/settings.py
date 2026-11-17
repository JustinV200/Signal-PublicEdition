"""load_config: config.toml over the code defaults, validated into a frozen ChamberConfig.

The TOML is flat (no tables). Path values may use %VAR% environment variables
(expanded with os.path.expandvars) and resolve against the repo root when
relative. Unknown keys and wrong types raise ConfigError naming the key.
config.example.toml lists every key with exactly these defaults (a test checks it).
"""

import os
import re
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from analysis_chamber.config.paths import DEFAULT_CONFIG_PATH, REPO_ROOT

DEFAULT_MODEL_OPUS = "claude-opus-5-5"
DEFAULT_MODEL_SONNET = "claude-sonnet-5-5"
# Number keys: (default, lowest allowed value).
INT_DEFAULTS: dict[str, tuple[int, int]] = {
    "max_parallel_runs": (3, 1),
    "critic_rounds_max": (2, 1),
}
STR_DEFAULTS: dict[str, str] = {
    "lead_model": DEFAULT_MODEL_OPUS,
    "critic_model": DEFAULT_MODEL_OPUS,
    "qa_model": DEFAULT_MODEL_OPUS,
    "fetch_model": DEFAULT_MODEL_SONNET,
}
# String keys that may be empty. signup_mail_account is the one mailbox the signup agent
# may read for verification mails; empty means chamber_get_api_key is off.
OPTIONAL_STR_DEFAULTS: dict[str, str] = {"signup_mail_account": ""}
# Raw path strings, resolved by _resolve_path the same way a TOML value is.
PATH_DEFAULTS: dict[str, str] = {
    "analyses_root": "life/analyses",
    "private_root": r"%USERPROFILE%\analysis-chamber-private",
    "kit_venv": r"%LOCALAPPDATA%\analysis-chamber\kit",
    "log_dir": r"%LOCALAPPDATA%\analysis-chamber",
    "state_dir": "tools/analysis-chamber/.state",
    "playbook_path": "tools/analysis-chamber/skills/playbook",
}
# A %NAME%, $NAME or ${NAME} left after os.path.expandvars means the variable isn't set.
_UNEXPANDED_VAR = re.compile(r"%[^%\\/]+%|\$\{[^}]*\}|\$\w+")
KNOWN_KEYS = (
    frozenset(INT_DEFAULTS)
    | frozenset(STR_DEFAULTS)
    | frozenset(OPTIONAL_STR_DEFAULTS)
    | frozenset(PATH_DEFAULTS)
)


class ConfigError(ValueError):
    """config.toml is unreadable or breaks a rule. The message names the key."""


@dataclass(frozen=True)
class ChamberConfig:
    """Every setting the chamber uses. Paths are absolute.

    Attributes:
        max_parallel_runs: Most runs active at once; more approved runs queue.
        critic_rounds_max: Most critic/fix rounds per run.
        lead_model, critic_model, qa_model, fetch_model: Model id per agent role.
        repo_root: The Signal repo (derived, not configurable).
        analyses_root: Where non-personal runs live (life/analyses).
        private_root: Where personal and not-yet-approved runs live, outside the repo.
        kit_venv: The shared analysis kit venv.
        log_dir: The daemon's rotating log folder.
        state_dir: Daemon state (daemon.json, gpu.lock).
        playbook_path: The methods playbook skill folder.
        signup_mail_account: The only mailbox (address) the signup agent may read; "" turns
            chamber_get_api_key off.
    """

    max_parallel_runs: int
    critic_rounds_max: int
    lead_model: str
    critic_model: str
    qa_model: str
    fetch_model: str
    repo_root: Path
    analyses_root: Path
    private_root: Path
    kit_venv: Path
    log_dir: Path
    state_dir: Path
    playbook_path: Path
    signup_mail_account: str = ""


def load_config(path: Path | None = None) -> ChamberConfig:
    """Read config.toml over the defaults; a missing file means all defaults.

    Args:
        path: The TOML file; None means tools/analysis-chamber/config.toml.

    Returns:
        The validated config.

    Raises:
        ConfigError: The file can't be parsed, or has an unknown key or a bad value.
    """
    raw = _read_toml(path or DEFAULT_CONFIG_PATH)
    unknown = sorted(set(raw) - KNOWN_KEYS)
    if unknown:
        raise ConfigError(f"config: unknown key(s) {', '.join(unknown)}")
    values: dict[str, Any] = {"repo_root": REPO_ROOT}
    for key, (default, minimum) in INT_DEFAULTS.items():
        values[key] = _check_int(key, raw.get(key, default), minimum)
    for key, default in STR_DEFAULTS.items():
        values[key] = _check_str(key, raw.get(key, default))
    for key, default in OPTIONAL_STR_DEFAULTS.items():
        values[key] = _check_optional_str(key, raw.get(key, default))
    for key, default in PATH_DEFAULTS.items():
        values[key] = _resolve_path(key, _check_str(key, raw.get(key, default)))
    return ChamberConfig(**values)


def _read_toml(path: Path) -> dict[str, Any]:
    """The parsed file, or {} when it doesn't exist."""
    try:
        with path.open("rb") as handle:
            return tomllib.load(handle)
    except FileNotFoundError:
        return {}
    except (OSError, tomllib.TOMLDecodeError) as error:
        raise ConfigError(f"config: can't read {path}: {error}") from error


def _check_int(key: str, value: object, minimum: int) -> int:
    """value if it's an int (not a bool) at or above minimum."""
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ConfigError(f"config: {key} must be an integer >= {minimum}, got {value!r}")
    return value


def _check_str(key: str, value: object) -> str:
    """value if it's a non-empty string."""
    if not isinstance(value, str) or not value.strip():
        raise ConfigError(f"config: {key} must be a non-empty string, got {value!r}")
    return value


def _check_optional_str(key: str, value: object) -> str:
    """value if it's a string (empty allowed), trimmed."""
    if not isinstance(value, str):
        raise ConfigError(f"config: {key} must be a string, got {value!r}")
    return value.strip()


def _resolve_path(key: str, value: str) -> Path:
    """Expand %VAR%s; a relative path resolves against the repo root.

    An unset variable stays literal after expandvars, and the path would then
    land inside the repo (e.g. the kit venv), so a leftover %NAME%, $NAME or
    ${NAME} is refused.
    """
    expanded = os.path.expandvars(value)
    leftover = _UNEXPANDED_VAR.search(expanded)
    if leftover:
        raise ConfigError(f"config: {key} uses unset environment variable {leftover.group()}")
    path = Path(expanded)
    return path if path.is_absolute() else REPO_ROOT / path
