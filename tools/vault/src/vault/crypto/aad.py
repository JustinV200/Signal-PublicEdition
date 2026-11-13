"""Canonical JSON encoding for AES-GCM associated data.

The store binds metadata (ids, origins, policy, unlock provider) into the
ciphertext by passing it as AAD. The encoding must be byte-for-byte stable, so
keys are sorted, separators are fixed and output is ASCII-only.
"""

import json
from collections.abc import Mapping
from typing import Any


def canonical_json(value: Mapping[str, Any]) -> bytes:
    """Encode `value` as canonical JSON bytes: sorted keys, no whitespace, ASCII.

    Args:
        value: A JSON-safe mapping.

    Returns:
        The encoded bytes, identical for equal inputs.

    Raises:
        TypeError: `value` holds something JSON can't encode.
    """
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode(
        "ascii"
    )
