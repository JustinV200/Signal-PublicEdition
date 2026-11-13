"""Hello unlocker with a fake signer (no Hello device): KEK derivation, determinism, wiping."""

import pytest

from vault.unlock import UnlockError
from vault.unlock.hello import HELLO_KEY_NAME, HelloUnlocker


class _RandomSigner:
    """Signs differently every time, like a non-deterministic signature scheme."""

    def __init__(self) -> None:
        self.calls = 0

    async def create_key(self, key_name: str) -> None:
        pass

    async def sign(self, key_name: str, challenge: bytes) -> bytearray:
        self.calls += 1
        return bytearray(challenge + bytes([self.calls]))


class _KeepingSigner:
    """Keeps every signature it hands out, to check the unlocker wipes them."""

    def __init__(self) -> None:
        self.handed_out: list[bytearray] = []

    async def create_key(self, key_name: str) -> None:
        pass

    async def sign(self, key_name: str, challenge: bytes) -> bytearray:
        signature = bytearray(b"sig:" + challenge)
        self.handed_out.append(signature)
        return signature


@pytest.mark.asyncio
async def test_enroll_and_unlock_derive_the_same_kek_per_challenge():
    unlocker = HelloUnlocker(_KeepingSigner())

    enrollment = await unlocker.enroll(b"a" * 32)
    again = await unlocker.derive_kek(b"a" * 32, enrollment.unlock_params)
    other = await unlocker.derive_kek(b"b" * 32, enrollment.unlock_params)

    assert enrollment.unlock_params == {"key_name": HELLO_KEY_NAME}
    assert again == enrollment.kek
    assert other != enrollment.kek


@pytest.mark.asyncio
async def test_non_deterministic_signatures_are_refused_at_enroll():
    with pytest.raises(UnlockError, match="not deterministic"):
        await HelloUnlocker(_RandomSigner()).enroll(b"a" * 32)


@pytest.mark.asyncio
async def test_signatures_are_wiped_after_deriving():
    signer = _KeepingSigner()

    await HelloUnlocker(signer).derive_kek(b"a" * 32, {"key_name": HELLO_KEY_NAME})

    assert signer.handed_out and not any(signer.handed_out[0])


@pytest.mark.asyncio
async def test_hello_is_supported_query_returns_a_bool():
    from vault.unlock.hello_winrt import is_hello_supported

    assert isinstance(await is_hello_supported(), bool)
