"""Data-key lifecycle: the DEK is wiped after use, and a tampered header can't be unwrapped."""

import dataclasses

import pytest

from vault.crypto import DecryptionError
from vault.store import create_vault_data, unlocked_dek
from vault.unlock.hello import HelloUnlocker


@pytest.mark.asyncio
async def test_dek_is_wiped_when_the_block_exits(fill_env):
    unlocker = HelloUnlocker(fill_env.signer)
    data = await create_vault_data(unlocker)

    async with unlocked_dek(data.header, unlocker) as dek:
        held = dek
        assert any(held)

    assert not any(held)


@pytest.mark.asyncio
async def test_a_replaced_challenge_fails_to_unwrap(fill_env):
    unlocker = HelloUnlocker(fill_env.signer)
    header = (await create_vault_data(unlocker)).header
    tampered = dataclasses.replace(header, challenge=b"x" * 32)

    with pytest.raises(DecryptionError):
        async with unlocked_dek(tampered, unlocker):
            pass
