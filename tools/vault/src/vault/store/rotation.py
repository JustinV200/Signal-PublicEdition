"""Remove a credential and re-seal everything else under a fresh data key.

Deleting a record alone isn't enough. The DEK would be unchanged, so a copy
of the old record (from a backup, or saved by an agent) pasted back into
store.json would still decrypt. Rotating the DEK makes that old record fail
verification (reported as `tampered`).

Limit: the KEK (unlock factor) is unchanged, so a full copy of the old
store.json, or its old `wrapped_dek` pasted back, still opens with the same
factor. Full revocation would need the unlock factor rotated too.
"""

import dataclasses

from vault.crypto import generate_key, open_sealed, seal, wipe
from vault.store.schema import CredentialRecord, VaultData, VaultHeader
from vault.store.sealing import open_credential, seal_credential
from vault.unlock import Unlocker


def _resealed(
    old_dek: bytearray, new_dek: bytearray, header: VaultHeader, record: CredentialRecord
) -> CredentialRecord:
    """Decrypt `record` under the old DEK and seal it again under the new one."""
    secrets = open_credential(old_dek, header, record)
    return seal_credential(
        new_dek, header, record.meta, secrets.username.reveal(), secrets.password.reveal()
    )


async def remove_and_rotate(data: VaultData, credential_id: str, unlocker: Unlocker) -> VaultData:
    """Return `data` without `credential_id`, with a new DEK and every other record re-sealed.

    The KEK is unchanged (same unlock factor); the new DEK is wrapped with a
    fresh nonce. Every key is wiped before returning. The caller saves the
    result (atomically, via save_vault).

    Args:
        data: The loaded vault.
        credential_id: The credential to remove; must exist.
        unlocker: The vault's unlocker (prompts the owner once).

    Returns:
        The rotated vault.

    Raises:
        KeyError: No such credential.
        UnlockError: The owner cancelled or the factor is unavailable.
        DecryptionError: Wrong factor, or the header was tampered with.
        TamperedRecordError: A remaining record doesn't verify (nothing is changed).
    """
    kept = data.without_record(credential_id).records
    header = data.header
    kek = await unlocker.derive_kek(header.challenge, header.unlock_params)
    old_dek, new_dek = None, generate_key()
    try:
        old_dek = bytearray(open_sealed(kek, header.wrapped_dek, header.aad()))
        new_header = dataclasses.replace(header, wrapped_dek=seal(kek, new_dek, header.aad()))
        records = tuple(_resealed(old_dek, new_dek, new_header, record) for record in kept)
    finally:
        wipe(kek)
        wipe(old_dek)
        wipe(new_dek)
    return VaultData(header=new_header, records=records)
