"""Tests for mail_digest.memory.lock: two runs can't hold the lock at once."""

import pytest

from mail_digest.memory import LockHeldError, is_locked, run_lock


def test_a_second_run_is_refused_until_the_first_releases_the_lock(tmp_path):
    lock_path = tmp_path / "state" / "run.lock"
    assert not is_locked(lock_path)
    with run_lock(lock_path):
        assert is_locked(lock_path)
        with pytest.raises(LockHeldError), run_lock(lock_path):
            pass
    assert not is_locked(lock_path)
