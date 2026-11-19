"""Convert `VaultData` to and from the JSON text of store.json, validating everything read.

The file is a trust boundary: an agent can edit it. Validation here catches
malformed input early; tampering with meaningful fields (origins, policy,
provider) is caught by AES-GCM AAD when the record is decrypted.
"""

import base64
import binascii
import json
from collections.abc import Mapping
from typing import Any

from vault.crypto import NONCE_BYTES, Sealed
from vault.origin import OriginError, parse_registered_origin
from vault.store.schema import (
    CHALLENGE_BYTES,
    CREDENTIAL_ID_PATTERN,
    FORMAT_VERSION,
    MAX_NAME_CHARS,
    CredentialMeta,
    CredentialRecord,
    VaultData,
    VaultHeader,
    b64,
)
from vault.unlock import PROVIDERS


class VaultFormatError(ValueError):
    """store.json is malformed or uses an unsupported format."""


def _sealed_to_json(sealed: Sealed) -> dict[str, str]:
    return {"nonce": b64(sealed.nonce), "ciphertext": b64(sealed.ciphertext)}


def _record_to_json(record: CredentialRecord) -> dict[str, Any]:
    meta = record.meta
    return {
        "id": meta.id,
        "name": meta.name,
        "origins": list(meta.origins),
        "username_hint": meta.username_hint,
        "policy": dict(meta.policy),
        "version": meta.version,
        **_sealed_to_json(record.sealed),
    }


def vault_to_json(data: VaultData) -> str:
    """Serialise `data` as indented JSON text (no secrets: ciphertext only)."""
    header = data.header
    document = {
        "version": header.version,
        "provider": header.provider,
        "challenge": b64(header.challenge),
        "unlock_params": dict(header.unlock_params),
        "wrapped_dek": _sealed_to_json(header.wrapped_dek),
        "credentials": [_record_to_json(record) for record in data.records],
    }
    return json.dumps(document, indent=2, sort_keys=True) + "\n"


def _decode_b64(value: Any, *, expected_len: int | None = None) -> bytes:
    """Decode a base64 string, optionally requiring an exact decoded length."""
    try:
        decoded = base64.b64decode(value, validate=True)
    except (TypeError, ValueError, binascii.Error):
        raise VaultFormatError("invalid base64 value") from None
    if expected_len is not None and len(decoded) != expected_len:
        raise VaultFormatError("base64 value has the wrong length")
    return decoded


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise VaultFormatError(message)


def _sealed_from_json(raw: Mapping[str, Any]) -> Sealed:
    return Sealed(
        nonce=_decode_b64(raw.get("nonce"), expected_len=NONCE_BYTES),
        ciphertext=_decode_b64(raw.get("ciphertext")),
    )


def _origins_from_json(raw: Any) -> tuple[str, ...]:
    """Origins must be a non-empty list of already-canonical https origins."""
    _require(isinstance(raw, list) and bool(raw), "origins must be a non-empty list")
    try:
        canonical = tuple(parse_registered_origin(origin) for origin in raw)
    except (OriginError, AttributeError):
        raise VaultFormatError("origins contain an invalid entry") from None
    _require(canonical == tuple(raw), "origins are not in canonical form")
    return canonical


def _record_from_json(raw: Any) -> CredentialRecord:
    _require(isinstance(raw, dict), "each credential must be an object")
    credential_id, name, hint = raw.get("id"), raw.get("name"), raw.get("username_hint")
    _require(
        isinstance(credential_id, str) and bool(CREDENTIAL_ID_PATTERN.match(credential_id)),
        "bad id",
    )
    _require(isinstance(name, str) and 0 < len(name) <= MAX_NAME_CHARS, "bad name")
    _require(isinstance(hint, str), "bad username_hint")
    policy = raw.get("policy")
    _require(
        isinstance(policy, dict) and all(isinstance(v, str) for v in policy.values()),
        "bad policy",
    )
    _require(raw.get("version") == FORMAT_VERSION, "unsupported credential version")
    meta = CredentialMeta(
        id=credential_id,
        name=name,
        origins=_origins_from_json(raw.get("origins")),
        username_hint=hint,
        policy=policy,
    )
    return CredentialRecord(meta=meta, sealed=_sealed_from_json(raw))


def _header_from_json(raw: Mapping[str, Any]) -> VaultHeader:
    _require(raw.get("version") == FORMAT_VERSION, "unsupported vault format version")
    _require(raw.get("provider") in PROVIDERS, "unknown unlock provider")
    _require(isinstance(raw.get("unlock_params"), dict), "unlock_params must be an object")
    _require(isinstance(raw.get("wrapped_dek"), dict), "wrapped_dek must be an object")
    return VaultHeader(
        version=FORMAT_VERSION,
        provider=raw["provider"],
        challenge=_decode_b64(raw.get("challenge"), expected_len=CHALLENGE_BYTES),
        unlock_params=raw["unlock_params"],
        wrapped_dek=_sealed_from_json(raw["wrapped_dek"]),
    )


def vault_from_json(text: str) -> VaultData:
    """Parse and validate store.json text.

    Raises:
        VaultFormatError: Malformed JSON, unknown version or provider, bad fields,
            or duplicate credential ids.
    """
    try:
        raw = json.loads(text)
    except json.JSONDecodeError:
        raise VaultFormatError("store.json is not valid JSON") from None
    _require(isinstance(raw, dict), "store.json must hold an object")
    _require(isinstance(raw.get("credentials"), list), "credentials must be a list")
    records = tuple(_record_from_json(item) for item in raw["credentials"])
    ids = [record.meta.id for record in records]
    _require(len(ids) == len(set(ids)), "duplicate credential ids")
    return VaultData(header=_header_from_json(raw), records=records)
