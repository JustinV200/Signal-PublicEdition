"""Credential sealing: every metadata field and the unlock provider are bound into the AAD."""

import dataclasses

import pytest

from vault.crypto import Sealed, generate_key
from vault.store import (
    DEFAULT_POLICY,
    CredentialMeta,
    CredentialRecord,
    TamperedRecordError,
    VaultHeader,
    open_credential,
    seal_credential,
)
from vault.unlock import PROVIDER_HELLO, PROVIDER_PASSPHRASE

META = CredentialMeta("github", "GitHub", ("https://github.com",), "j***", DEFAULT_POLICY)


def _header(provider: str) -> VaultHeader:
    return VaultHeader(1, provider, b"c" * 32, {}, Sealed(b"n" * 12, b""))


def test_sealed_login_opens_with_matching_metadata():
    dek = generate_key()
    record = seal_credential(dek, _header(PROVIDER_HELLO), META, "jdoe", "pw")

    secrets = open_credential(dek, _header(PROVIDER_HELLO), record)

    assert (secrets.username.reveal(), secrets.password.reveal()) == ("jdoe", "pw")


@pytest.mark.parametrize(
    "tampered",
    [
        {"origins": ("https://github.com", "https://evil.test")},
        {"name": "Something else"},
        {"username_hint": "x***"},
        {"id": "gitlab"},
    ],
)
def test_editing_any_metadata_field_breaks_decryption(tampered):
    dek = generate_key()
    record = seal_credential(dek, _header(PROVIDER_HELLO), META, "jdoe", "pw")
    edited = CredentialRecord(meta=dataclasses.replace(META, **tampered), sealed=record.sealed)

    with pytest.raises(TamperedRecordError):
        open_credential(dek, _header(PROVIDER_HELLO), edited)


def test_a_different_unlock_provider_breaks_decryption():
    dek = generate_key()
    record = seal_credential(dek, _header(PROVIDER_HELLO), META, "jdoe", "pw")

    with pytest.raises(TamperedRecordError):
        open_credential(dek, _header(PROVIDER_PASSPHRASE), record)
