"""`mail check` fails with words, a fix and a command when no sign-in is usable, offline."""

import json
from pathlib import Path

from mail_tool.cli import check, main


def run_check(monkeypatch, capsys, accounts: Path) -> tuple[int, dict]:
    monkeypatch.setattr(check, "ACCOUNTS_DIR", accounts)
    code = main(["check"])
    return code, json.loads(capsys.readouterr().out.splitlines()[-1])


def test_no_account_fails_with_a_fix(monkeypatch, capsys, tmp_path: Path) -> None:
    code, summary = run_check(monkeypatch, capsys, tmp_path / "none")
    assert code == 1 and "No Gmail account" in summary["words"] and summary["fix"]


def test_unreadable_sign_in_fails_naming_the_account(monkeypatch, capsys, tmp_path: Path) -> None:
    (tmp_path / "personal.bin").write_bytes(b"not a dpapi blob")
    code, summary = run_check(monkeypatch, capsys, tmp_path)
    assert code == 1 and "personal" in summary["words"]
    assert summary["command"].endswith("mail add personal")
