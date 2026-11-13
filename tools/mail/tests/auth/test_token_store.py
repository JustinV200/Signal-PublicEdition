"""Tests for TokenStore: DPAPI round trip, atomic owner-only writes, alias safety."""

import getpass
import os
import subprocess
from pathlib import Path

import pytest
from support.fakes import SECRET_REFRESH_TOKEN

from mail_tool.auth import AccountRecord, TokenStore
from mail_tool.errors import AccountError, ReauthRequired

pytestmark = pytest.mark.skipif(os.name != "nt", reason="DPAPI is Windows-only")


def test_round_trip_keeps_the_token_encrypted_at_rest(tmp_path: Path) -> None:
    store = TokenStore(tmp_path / "accounts")
    record = AccountRecord("personal", "owner@example.com", SECRET_REFRESH_TOKEN)

    store.save(record)

    on_disk = (tmp_path / "accounts" / "personal.bin").read_bytes()
    assert SECRET_REFRESH_TOKEN.encode() not in on_disk
    assert store.load("personal") == record
    assert store.find("owner@example.com") == record
    assert store.aliases() == ["personal"]
    assert SECRET_REFRESH_TOKEN not in repr(record)
    assert store.remove("personal") and store.aliases() == []


def test_replacing_an_account_is_atomic_and_keeps_the_owner_only_acl(tmp_path: Path) -> None:
    store = TokenStore(tmp_path)
    store.save(AccountRecord("alt", "old@example.com", "old-token"))

    store.save(AccountRecord("alt", "owner.alt@example.com", SECRET_REFRESH_TOKEN))

    assert store.load("alt").refresh_token == SECRET_REFRESH_TOKEN
    assert [p.name for p in tmp_path.iterdir()] == ["alt.bin"]  # no temp file left behind
    path = str(tmp_path / "alt.bin")
    acl = subprocess.run(["icacls", path], capture_output=True, text=True, check=True).stdout
    entries = [line.strip() for line in acl.replace(path, "").splitlines() if ":(" in line]
    # One explicit full-control entry for this user: nothing inherited from the folder.
    assert len(entries) == 1
    assert entries[0].lower().endswith(f"\\{getpass.getuser().lower()}:(f)")


def test_corrupt_blob_needs_reauth_and_bad_aliases_are_refused(tmp_path: Path) -> None:
    store = TokenStore(tmp_path)
    (tmp_path / "alt.bin").write_bytes(b"not a dpapi blob")

    with pytest.raises(ReauthRequired, match="re-run `mail add alt`"):
        store.load("alt")
    for bad in ("../escape", "a/b", "", "x" * 33):
        with pytest.raises(AccountError):
            store.load(bad)
