"""Seal and open one credential's {username, password} under the data key.

The AAD is the record's own metadata plus the vault's unlock provider, so
editing an origin, the name, the hint or the policy in store.json makes the
record undecryptable.
"""

import json
from dataclasses import dataclass

from vault.crypto import DecryptionError, open_sealed, seal
from vault.secret import Secret
from vault.store.schema import CredentialMeta, CredentialRecord, VaultHeader

USERNAME_KEY = "username"
PASSWORD_KEY = "password"


class TamperedRecordError(Exception):
    """The vault unlocked, but this record's ciphertext or metadata doesn't verify."""


@dataclass(frozen=True)
class LoginSecrets:
    """A decrypted login, still wrapped so reprs and logs can't show it."""

    username: Secret
    password: Secret


def seal_credential(
    dek: bytearray, header: VaultHeader, meta: CredentialMeta, username: str, password: str
) -> CredentialRecord:
    """Encrypt a username and password into a record bound to `meta`.

    Args:
        dek: The unwrapped data key.
        header: The vault header (its provider is bound into the AAD).
        meta: The record's metadata.
        username: Plaintext username.
        password: Plaintext password.

    Returns:
        The new record.
    """
    payload = json.dumps({USERNAME_KEY: username, PASSWORD_KEY: password}).encode("utf-8")
    return CredentialRecord(meta=meta, sealed=seal(dek, payload, meta.aad(header.provider)))


def open_credential(dek: bytearray, header: VaultHeader, record: CredentialRecord) -> LoginSecrets:
    """Decrypt `record`, verifying its metadata.

    Raises:
        TamperedRecordError: The ciphertext or any AAD-bound field was changed.
    """
    try:
        payload = open_sealed(dek, record.sealed, record.meta.aad(header.provider))
    except DecryptionError:
        raise TamperedRecordError(f"credential {record.meta.id!r} failed verification") from None
    values = json.loads(payload)
    del payload
    return LoginSecrets(
        username=Secret(values[USERNAME_KEY]), password=Secret(values[PASSWORD_KEY])
    )
