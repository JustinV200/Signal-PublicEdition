"""AES-GCM sealing: a fresh nonce every time, and AAD that must match exactly."""

import pytest

from vault.crypto import NONCE_BYTES, DecryptionError, generate_key, open_sealed, seal


def test_every_encryption_uses_a_fresh_nonce():
    key = generate_key()

    sealed = [seal(key, b"same plaintext", b"aad") for _ in range(500)]

    nonces = {item.nonce for item in sealed}
    assert len(nonces) == len(sealed)
    assert all(len(nonce) == NONCE_BYTES for nonce in nonces)
    assert len({item.ciphertext for item in sealed}) == len(sealed)


def test_changed_aad_or_key_fails_to_decrypt():
    key = generate_key()
    sealed = seal(key, b"secret", b'{"origins":["https://a.test"]}')

    assert open_sealed(key, sealed, b'{"origins":["https://a.test"]}') == b"secret"
    with pytest.raises(DecryptionError):
        open_sealed(key, sealed, b'{"origins":["https://a.test","https://evil.test"]}')
    with pytest.raises(DecryptionError):
        open_sealed(generate_key(), sealed, b'{"origins":["https://a.test"]}')
