"""Owner-only secret files: a secret is never written into a file that couldn't be locked."""

import os
import subprocess

import pytest

from signal_console.state_files import write_secret


@pytest.mark.skipif(os.name != "nt", reason="icacls is the Windows lock")
def test_secret_isnt_written_when_its_file_cant_be_locked(tmp_path, monkeypatch):
    secret_path = tmp_path / "local-key"
    real_run = subprocess.run

    def icacls_refusing_the_file(command, **kwargs):
        if command[1] == str(secret_path):
            return subprocess.CompletedProcess(command, 5, "", "Access is denied.")
        return real_run(command, **kwargs)

    monkeypatch.setattr(subprocess, "run", icacls_refusing_the_file)

    with pytest.raises(OSError, match="couldn't restrict"):
        write_secret(secret_path, "s3cret")
    assert "s3cret" not in secret_path.read_text(encoding="utf-8")
