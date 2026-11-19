"""`vault policy` re-seals the record: the new policy verifies, and a hand edit would not."""

import asyncio
import json

from vault.cli.main import main
from vault.store import load_vault, open_credential, unlocked_dek
from vault.unlock.hello import HelloUnlocker


async def _password(cli) -> str:
    data = load_vault(cli.store_path)
    async with unlocked_dek(data.header, HelloUnlocker(cli.signer)) as dek:
        return open_credential(dek, data.header, data.records[0]).password.reveal()


def test_policy_sets_confirm_and_keeps_the_record_openable(cli):
    assert main(["policy", "example", "--confirm", "never"], cli.context()) == 0

    saved = json.loads(cli.store_path.read_text(encoding="utf-8"))["credentials"][0]
    assert saved["policy"] == {"confirm": "never"}
    assert asyncio.run(_password(cli))
    assert main(["policy", "nope", "--confirm", "always"], cli.context()) == 2
