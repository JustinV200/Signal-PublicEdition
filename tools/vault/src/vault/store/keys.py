"""Data-key lifecycle: create a vault's wrapped data key, and unwrap it for one operation.

KEK (from the unlocker) --AES-GCM, AAD = header--> DEK --AES-GCM, AAD = record--> credentials.

The DEK only exists inside `unlocked_dek`, which wipes it on exit. Callers
decrypt what they need inside the block and leave before any slow or
exception-prone work (like a Playwright fill).
"""

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from vault.crypto import generate_key, open_sealed, seal, wipe
from vault.store.schema import CHALLENGE_BYTES, FORMAT_VERSION, VaultData, VaultHeader, header_aad
from vault.unlock import Unlocker


async def create_vault_data(unlocker: Unlocker) -> VaultData:
    """Enroll the unlocker and return an empty vault whose DEK is wrapped by its KEK.

    Raises:
        UnlockError: The owner cancelled or the factor is unavailable.
    """
    challenge = os.urandom(CHALLENGE_BYTES)
    enrollment = await unlocker.enroll(challenge)
    dek = generate_key()
    try:
        aad = header_aad(FORMAT_VERSION, unlocker.provider, challenge, enrollment.unlock_params)
        wrapped = seal(enrollment.kek, dek, aad)
    finally:
        wipe(enrollment.kek)
        wipe(dek)
    header = VaultHeader(
        version=FORMAT_VERSION,
        provider=unlocker.provider,
        challenge=challenge,
        unlock_params=enrollment.unlock_params,
        wrapped_dek=wrapped,
    )
    return VaultData(header=header)


@asynccontextmanager
async def unlocked_dek(header: VaultHeader, unlocker: Unlocker) -> AsyncIterator[bytearray]:
    """Prompt the owner via `unlocker`, unwrap the DEK, yield it, then wipe it.

    Raises:
        UnlockError: The owner cancelled or the factor is unavailable.
        DecryptionError: Wrong factor, or the header was tampered with.
    """
    kek = await unlocker.derive_kek(header.challenge, header.unlock_params)
    try:
        dek = bytearray(open_sealed(kek, header.wrapped_dek, header.aad()))
    finally:
        wipe(kek)
    try:
        yield dek
    finally:
        wipe(dek)
