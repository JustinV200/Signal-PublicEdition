"""scrypt: explicit maxmem, and cost parameters from disk are bounds-checked."""

import hashlib

import pytest

from vault.crypto import ScryptParams, kdf, scrypt_key

FAST_PARAMS = ScryptParams(n=2**14)


def test_scrypt_passes_an_explicit_maxmem(monkeypatch):
    seen = {}
    real_scrypt = hashlib.scrypt

    def recording_scrypt(*args, **kwargs):
        seen.update(kwargs)
        return real_scrypt(*args, **kwargs)

    monkeypatch.setattr(kdf.hashlib, "scrypt", recording_scrypt)

    key = scrypt_key(bytearray(b"passphrase"), salt=b"s" * 32, params=FAST_PARAMS)

    assert seen["maxmem"] == kdf.SCRYPT_MAXMEM_BYTES
    assert len(key) == kdf.DERIVED_KEY_BYTES


@pytest.mark.parametrize(
    "params",
    [ScryptParams(n=2**30), ScryptParams(n=2**2), ScryptParams(n=3 * 2**14), ScryptParams(p=64)],
)
def test_out_of_bounds_scrypt_params_are_refused(params):
    with pytest.raises(ValueError):
        scrypt_key(b"passphrase", salt=b"s" * 32, params=params)
