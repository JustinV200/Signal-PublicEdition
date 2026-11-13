"""`vault init`: never overwrites an existing vault; a fresh one records its unlock method."""

import json

from vault.cli.main import EXIT_USER_ERROR, main


def test_init_refuses_to_overwrite_an_existing_vault(cli, capsys):
    before = cli.store_path.read_text(encoding="utf-8")

    assert main(["init"], cli.context()) == EXIT_USER_ERROR

    assert "already exists" in capsys.readouterr().err
    assert cli.store_path.read_text(encoding="utf-8") == before


def test_init_creates_an_empty_vault_bound_to_hello(cli):
    cli.store_path.unlink()

    assert main(["init"], cli.context()) == 0

    document = json.loads(cli.store_path.read_text(encoding="utf-8"))
    assert document["provider"] == "hello"
    assert document["credentials"] == []
