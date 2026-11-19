"""store.json parsing: a round trip, and malformed or non-canonical input is refused."""

import json

import pytest

from vault.store import VaultFormatError, load_vault
from vault.store.codec import vault_from_json, vault_to_json


@pytest.mark.asyncio
async def test_store_round_trips_without_plaintext(fill_env):
    text = fill_env.store_path.read_text(encoding="utf-8")

    assert vault_to_json(vault_from_json(text)) == text
    assert fill_env.password not in text
    assert fill_env.username not in text


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("credentials", 0, "origins"), ["https://LOGIN.example.test"]),
        (("credentials", 0, "origins"), ["https://login.example.test/path"]),
        (("credentials", 0, "nonce"), "AAAA"),
        (("credentials", 0, "policy"), "never"),
        (("provider",), "none"),
    ],
)
@pytest.mark.asyncio
async def test_malformed_fields_are_refused(fill_env, path, value):
    document = json.loads(fill_env.store_path.read_text(encoding="utf-8"))
    target = document
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    fill_env.store_path.write_text(json.dumps(document), encoding="utf-8")

    with pytest.raises(VaultFormatError):
        load_vault(fill_env.store_path)
