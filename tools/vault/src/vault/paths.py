"""Default locations of the vault's data files.

Both files live in %LOCALAPPDATA%\\signal-vault, outside the repo, so they can
never be committed. Tests and the CLI pass explicit paths instead.
"""

import os
from pathlib import Path

DATA_DIR_NAME = "signal-vault"
STORE_FILE_NAME = "store.json"
AUDIT_FILE_NAME = "audit.jsonl"
LOCAL_APPDATA_VAR = "LOCALAPPDATA"


def default_data_dir() -> Path:
    """Return %LOCALAPPDATA%\\signal-vault.

    Raises:
        RuntimeError: LOCALAPPDATA is not set (not a normal Windows session).
    """
    base = os.environ.get(LOCAL_APPDATA_VAR)
    if not base:
        raise RuntimeError(
            f"{LOCAL_APPDATA_VAR} is not set; the vault needs a Windows user profile"
        )
    return Path(base) / DATA_DIR_NAME


def default_store_path() -> Path:
    """Return the path of the encrypted credential store."""
    return default_data_dir() / STORE_FILE_NAME


def default_audit_path() -> Path:
    """Return the path of the append-only audit log."""
    return default_data_dir() / AUDIT_FILE_NAME
