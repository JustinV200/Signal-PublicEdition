"""Re-seal records under a fresh data key (to remove one, or to change a record's metadata).

Deleting a record alone isn't enough (the same goes for changing its policy:
an old copy sealed under the old metadata must stop verifying). The DEK would
be unchanged, so a copy of the old record (from a backup, or saved by an
agent) pasted back into store.json would still decrypt. Rotating the DEK
makes that old record fail verification (reported as `tampered`).

Limit: the KEK (unlock factor) is unchanged, so a full copy of the old
store.json, or its old `wrapped_dek` pasted back, still opens with the same
factor. Full revocation would need the unlock factor rotated too.
"""

import dataclasses
from collections.abc import Callable, Sequence

from vault.crypto import generate_key, open_sealed, seal, wipe
from vault.store.schema import CredentialMeta, CredentialRecord, VaultData, VaultHeader
from vault.store.sealing import open_credential, seal_credential
from vault.unlock import Unlocker


def _resealed(
    old_dek: bytearray,
    new_dek: bytearray,
    header: VaultHeader,
    record: CredentialRecord,
    edit_meta: Callable[[CredentialMeta], CredentialMeta],
) -> CredentialRecord:
    """Decrypt `record` under the old DEK and seal it again, edited, under the new one."""
    secrets = open_credential(old_dek, header, record)
    username, password = secrets.username.reveal(), secrets.password.reveal()
    return seal_credential(new_dek, header, edit_meta(record.meta), username, password)


async def remove_and_rotate(data: VaultData, credential_id: str, unlocker: Unlocker) -> VaultData:
    """Return `data` without `credential_id`, with a new DEK and every other record re-sealed.

    Raises KeyError if there is no such credential; otherwise see `rotate_records`.
    """
    return await rotate_records(data, data.without_record(credential_id).records, unlocker)


async def rotate_records(
    data: VaultData,
    records: Sequence[CredentialRecord],
    unlocker: Unlocker,
    edit_meta: Callable[[CredentialMeta], CredentialMeta] = lambda meta: meta,
) -> VaultData:
    """Return a vault holding `records` re-sealed (with `edit_meta` applied) under a new DEK.

    The KEK is unchanged (same unlock factor); the new DEK is wrapped with a
    fresh nonce. Every key is wiped before returning. The caller saves the
    result (atomically, via save_vault).

    Args:
        data: The loaded vault.
        records: The records to keep, taken from `data`.
        unlocker: The vault's unlocker (prompts the owner once).
        edit_meta: Returns the metadata each record is re-sealed with (default: unchanged).

    Returns:
        The rotated vault.

    Raises:
        UnlockError: The owner cancelled or the factor is unavailable.
        DecryptionError: Wrong factor, or the header was tampered with.
        TamperedRecordError: A remaining record doesn't verify (nothing is changed).
    """
    header = data.header
    kek = await unlocker.derive_kek(header.challenge, header.unlock_params)
    old_dek, new_dek = None, generate_key()
    try:
        old_dek = bytearray(open_sealed(kek, header.wrapped_dek, header.aad()))
        new_header = dataclasses.replace(header, wrapped_dek=seal(kek, new_dek, header.aad()))
        records = tuple(
            _resealed(old_dek, new_dek, new_header, record, edit_meta) for record in records
        )
    finally:
        wipe(kek)
        wipe(old_dek)
        wipe(new_dek)
    return VaultData(header=new_header, records=records)
