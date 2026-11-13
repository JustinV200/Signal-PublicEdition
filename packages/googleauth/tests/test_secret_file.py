"""Tests for write_secret_atomically and DPAPI: atomic, owner-only, encrypted round trip."""

import getpass
import os
import subprocess
from pathlib import Path

import pytest

from signal_googleauth import DpapiError, protect, unprotect, write_secret_atomically

pytestmark = pytest.mark.skipif(os.name != "nt", reason="DPAPI and icacls are Windows-only")

ENTROPY = b"signal/tests/v1"


def test_replacing_a_secret_is_atomic_owner_only_and_encrypted(tmp_path: Path) -> None:
    path = tmp_path / "token.bin"
    write_secret_atomically(path, protect(b"old", ENTROPY))

    write_secret_atomically(path, protect(b"new-secret", ENTROPY))

    assert b"new-secret" not in path.read_bytes()
    assert unprotect(path.read_bytes(), ENTROPY) == b"new-secret"
    assert [p.name for p in tmp_path.iterdir()] == ["token.bin"]  # no temp file left behind
    acl = subprocess.run(["icacls", str(path)], capture_output=True, text=True, check=True).stdout
    entries = [line.strip() for line in acl.replace(str(path), "").splitlines() if ":(" in line]
    # One explicit full-control entry for this user: nothing inherited from the folder.
    assert len(entries) == 1
    assert entries[0].lower().endswith(f"\\{getpass.getuser().lower()}:(f)")
    with pytest.raises(DpapiError):
        unprotect(path.read_bytes(), b"other-tool")
