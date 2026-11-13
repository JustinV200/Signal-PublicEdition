"""Tests for mail_digest.kb.review: a flagged file is reviewed only once git shows it clean."""

import shutil
import subprocess

import pytest

from mail_digest.kb import is_reviewed

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="needs git")


def _git(repo, *args):
    identity = ("-c", "user.name=test", "-c", "user.email=test@example.invalid")
    subprocess.run(["git", "-C", str(repo), *identity, *args], check=True, capture_output=True)


def test_only_a_committed_unchanged_file_is_reviewed(tmp_path):
    outside = tmp_path / "not-a-repo"
    outside.mkdir()
    (outside / "inbox.md").write_text("# Inbox\n", encoding="utf-8")
    assert not is_reviewed(outside, "inbox.md")  # git can't answer: stays flagged

    life = tmp_path / "repo" / "life"
    life.mkdir(parents=True)
    _git(life.parent, "init", "-q")
    (life / "inbox.md").write_text("# Inbox\n", encoding="utf-8")
    assert not is_reviewed(life, "inbox.md")  # untracked
    _git(life.parent, "add", "life/inbox.md")
    _git(life.parent, "commit", "-q", "-m", "inbox")
    assert is_reviewed(life, "inbox.md")
    (life / "inbox.md").write_text("# Inbox\n- planted (mail)\n", encoding="utf-8")
    assert not is_reviewed(life, "inbox.md")
