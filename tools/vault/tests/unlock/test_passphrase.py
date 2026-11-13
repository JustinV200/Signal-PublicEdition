"""Passphrase unlocker with a fake prompt, real scrypt and real DPAPI."""

import pytest

from vault.crypto import ScryptParams
from vault.unlock import UnlockError
from vault.unlock.passphrase import PassphraseUnlocker

FAST_PARAMS = ScryptParams(n=2**14)
CHALLENGE = b"c" * 32


def _prompt_returning(*answers: bytes | None):
    queue = list(answers)
    return lambda _request: None if (answer := queue.pop(0)) is None else bytearray(answer)


@pytest.mark.asyncio
async def test_same_passphrase_gives_the_same_kek_and_a_wrong_one_does_not():
    good = b"correct horse battery"
    unlocker = PassphraseUnlocker(
        _prompt_returning(good, good, b"wrong horse battery"), FAST_PARAMS
    )

    enrollment = await unlocker.enroll(CHALLENGE)
    assert "correct" not in str(enrollment.unlock_params)
    assert await unlocker.derive_kek(CHALLENGE, enrollment.unlock_params) == enrollment.kek
    assert await unlocker.derive_kek(CHALLENGE, enrollment.unlock_params) != enrollment.kek


@pytest.mark.asyncio
async def test_cancelled_or_short_passphrases_are_refused():
    with pytest.raises(UnlockError):
        await PassphraseUnlocker(_prompt_returning(None), FAST_PARAMS).enroll(CHALLENGE)
    with pytest.raises(UnlockError, match="at least"):
        await PassphraseUnlocker(_prompt_returning(b"short"), FAST_PARAMS).enroll(CHALLENGE)
