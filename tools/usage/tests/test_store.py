"""Tests for the state file's locked write: stale-lock breaking, the bounded wait, many writers."""

import contextlib
import os
import threading
import time

import pytest

from usage.store import STALE_LOCK_S, StateLockTimeoutError, read_state, update_state
from usage.times import local_now

WAIT_S = 0.2
OLD_LOCK_AGE_S = STALE_LOCK_S + 60


def _count_write(state, at):
    return {**state, "writes": state.get("writes", 0) + 1}


@pytest.mark.parametrize(
    ("lock_age_s", "is_deletable", "is_broken"),
    [
        pytest.param(OLD_LOCK_AGE_S, True, True, id="old-lock-is-broken"),
        pytest.param(0, True, False, id="fresh-lock-times-out"),
        pytest.param(OLD_LOCK_AGE_S, False, False, id="undeletable-lock-times-out"),
    ],
)
def test_old_lock_is_broken_otherwise_the_wait_is_bounded(
    lock_age_s, is_deletable, is_broken, tmp_path
):
    state_file = tmp_path / "usage.json"
    lock_file = tmp_path / "usage.json.lock"
    if is_deletable:
        lock_file.touch()
    else:
        lock_file.mkdir()  # unlink() fails on a folder, as on a read-only or delete-pending lock
    lock_time = time.time() - lock_age_s
    os.utime(lock_file, (lock_time, lock_time))

    started = time.monotonic()
    expected = contextlib.nullcontext() if is_broken else pytest.raises(StateLockTimeoutError)
    with expected:
        update_state(state_file, _count_write, local_now(), WAIT_S)
    assert time.monotonic() - started < WAIT_S + 1.0
    assert state_file.exists() is is_broken


def test_concurrent_writers_lose_no_updates(tmp_path):
    state_file = tmp_path / "usage.json"
    writers = [
        threading.Thread(target=update_state, args=(state_file, _count_write, local_now()))
        for _ in range(12)
    ]
    for writer in writers:
        writer.start()
    for writer in writers:
        writer.join()
    assert read_state(state_file)["writes"] == 12
