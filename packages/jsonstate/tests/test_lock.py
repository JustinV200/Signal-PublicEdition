"""Tests for state_lock: a writer that can't get the lock fails with StateFileError."""

import msvcrt
import os

import pytest

from signal_jsonstate import StateFileError, read_json_object, state_lock, write_json_atomic


def test_a_writer_fails_with_state_file_error_while_another_handle_holds_the_lock(
    tmp_path, monkeypatch
) -> None:
    lock_path = tmp_path / "state" / "x.lock"
    lock_path.parent.mkdir()
    monkeypatch.setattr("signal_jsonstate.lock.LOCK_WAIT_S", 0.05)  # not the real 2 s
    other = os.open(lock_path, os.O_RDWR | os.O_CREAT)  # another process's handle
    try:
        msvcrt.locking(other, msvcrt.LK_NBLCK, 1)
        with pytest.raises(StateFileError), state_lock(lock_path):
            pass
        os.lseek(other, 0, os.SEEK_SET)
        msvcrt.locking(other, msvcrt.LK_UNLCK, 1)
    finally:
        os.close(other)
    with state_lock(lock_path):
        write_json_atomic(tmp_path / "state" / "x.json", {"a": 1})
    assert read_json_object(tmp_path / "state" / "x.json") == {"a": 1}
