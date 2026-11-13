"""`vault remove` revokes: a saved copy of the removed record no longer decrypts."""

import asyncio
import json

import pytest

from vault.cli.main import main
from vault.store import TamperedRecordError, load_vault, open_credential, unlocked_dek
from vault.unlock.hello import HelloUnlocker


async def _open(cli, credential_id: str):
    data = load_vault(cli.store_path)
    async with unlocked_dek(data.header, HelloUnlocker(cli.signer)) as dek:
        return open_credential(dek, data.header, data.find(credential_id))


def test_a_removed_record_pasted_back_fails_as_tampered(cli):
    cli.secrets = ["forum-user", "forum-user", "Forum-Pa55!", "Forum-Pa55!"]
    main(
        ["add", "forum", "--name", "Forum", "--origin", "https://forum.example.test"], cli.context()
    )
    saved = json.loads(cli.store_path.read_text(encoding="utf-8"))["credentials"][0]
    assert saved["id"] == "example"

    cli.answers = ["example"]
    assert main(["remove", "example"], cli.context()) == 0
    document = json.loads(cli.store_path.read_text(encoding="utf-8"))
    document["credentials"].append(saved)
    cli.store_path.write_text(json.dumps(document), encoding="utf-8")

    with pytest.raises(TamperedRecordError):
        asyncio.run(_open(cli, "example"))
    assert asyncio.run(_open(cli, "forum")).password.reveal() == "Forum-Pa55!"
