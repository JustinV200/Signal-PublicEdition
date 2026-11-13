"""Read and atomically write store.json.

Writes go to a temporary file in the same folder and are then swapped in with
os.replace, so a crash mid-write never leaves a half-written store.
"""

import os
from pathlib import Path

from vault.store.codec import vault_from_json, vault_to_json
from vault.store.schema import VaultData

TEMP_SUFFIX = ".tmp"


class VaultNotInitializedError(FileNotFoundError):
    """There is no store.json yet; the owner needs to run `vault init`."""


def vault_exists(path: Path) -> bool:
    """Return True if a store file exists at `path`."""
    return path.is_file()


def load_vault(path: Path) -> VaultData:
    """Load and validate the vault at `path` (metadata and ciphertext; nothing is decrypted).

    Raises:
        VaultNotInitializedError: No file at `path`.
        VaultFormatError: The file is malformed.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise VaultNotInitializedError(f"no vault at {path}; run `vault init`") from None
    return vault_from_json(text)


def save_vault(path: Path, data: VaultData) -> None:
    """Write `data` to `path` atomically, creating the folder if needed.

    Raises:
        OSError: The file can't be written.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(path.name + TEMP_SUFFIX)
    with open(temp_path, "w", encoding="utf-8") as temp_file:
        temp_file.write(vault_to_json(data))
        # Flush to disk before the rename: after a power loss NTFS can keep the
        # rename but lose the data, leaving an empty store (and no wrapped DEK).
        temp_file.flush()
        os.fsync(temp_file.fileno())
    os.replace(temp_path, path)
