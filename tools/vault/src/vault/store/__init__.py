"""The local encrypted credential store (Option B): store.json, its key hierarchy and records.

Nothing here prompts or touches a browser. The fill path and the owner CLI
compose these pieces.
"""

from vault.store.codec import VaultFormatError
from vault.store.hints import username_hint
from vault.store.keys import create_vault_data, unlocked_dek
from vault.store.rotation import remove_and_rotate
from vault.store.schema import (
    CREDENTIAL_ID_PATTERN,
    DEFAULT_POLICY,
    MAX_NAME_CHARS,
    CredentialMeta,
    CredentialRecord,
    VaultData,
    VaultHeader,
)
from vault.store.sealing import LoginSecrets, TamperedRecordError, open_credential, seal_credential
from vault.store.vault_file import VaultNotInitializedError, load_vault, save_vault, vault_exists

__all__ = [
    "CREDENTIAL_ID_PATTERN",
    "DEFAULT_POLICY",
    "MAX_NAME_CHARS",
    "CredentialMeta",
    "CredentialRecord",
    "LoginSecrets",
    "TamperedRecordError",
    "VaultData",
    "VaultFormatError",
    "VaultHeader",
    "VaultNotInitializedError",
    "create_vault_data",
    "load_vault",
    "open_credential",
    "remove_and_rotate",
    "save_vault",
    "seal_credential",
    "unlocked_dek",
    "username_hint",
    "vault_exists",
]
