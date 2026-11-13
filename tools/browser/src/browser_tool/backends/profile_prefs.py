"""Turn off the browser's own password and autofill saving in the automation profile.

The vault is the only place credentials should live. If Edge offered to save a
password the vault just filled, the secret would be copied into the profile
(which also holds live session cookies). The prefs are merged into
<profile>/Default/Preferences before every launch of the local backend. Docker
jobs get the same settings from Edge managed policies in the image instead.

Verified on Edge 155 via edge://prefs-internals: Edge reads
credentials_enable_service and credentials_enable_autofill_passwords. Edge does not
register Chrome's legacy profile.password_manager_enabled; it is kept so the same
profile also behaves with channel="chrome".
"""

import json
import os
from pathlib import Path
from typing import Any

PREFERENCES_PATH = Path("Default") / "Preferences"

DISABLED_SAVING_PREFS: dict[str, Any] = {
    "credentials_enable_service": False,
    "credentials_enable_autofill_passwords": False,
    "credentials_enable_passwordgeneration": False,
    "autofill": {"profile_enabled": False, "credit_card_enabled": False},
    "profile": {"password_manager_enabled": False},
}


def disable_password_saving(profile_dir: Path) -> Path:
    """Merge DISABLED_SAVING_PREFS into the profile's Preferences file.

    Args:
        profile_dir: The persistent user-data dir (created if missing).

    Returns:
        The Preferences file path.

    Raises:
        ValueError: If an existing Preferences file is not a JSON object. It is left
            untouched so the owner can inspect it.
        OSError: If the file can't be read or written.
    """
    path = profile_dir / PREFERENCES_PATH
    current = _read_preferences(path)
    merged = merge_prefs(current, DISABLED_SAVING_PREFS)
    path.parent.mkdir(parents=True, exist_ok=True)
    # Write then rename, so a crash never leaves a half-written Preferences file.
    temporary = path.with_name(path.name + ".signal-tmp")
    temporary.write_text(json.dumps(merged), encoding="utf-8")
    os.replace(temporary, path)
    return path


def merge_prefs(current: dict[str, Any], overrides: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of `current` with `overrides` merged in, recursing into dicts."""
    merged = dict(current)
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = merge_prefs(merged[key], value)
        else:
            merged[key] = value
    return merged


def _read_preferences(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError(f"{path} is not valid JSON: {error}") from error
    if not isinstance(data, dict):
        raise ValueError(f"{path} is not a JSON object")
    return data
