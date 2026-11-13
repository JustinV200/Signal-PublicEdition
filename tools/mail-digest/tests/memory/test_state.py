"""Tests for mail_digest.memory.state: windows, retries, failures and announced-key memory."""

import pytest

from mail_digest.memory import (
    DigestState,
    KeyRetention,
    Lookback,
    Window,
    advance_windows,
    load_state,
    record_failure,
    remember_announced,
    save_state,
    search_windows,
)

MINUTE = 60
HOUR = 3600
DAY = 24 * HOUR
LOOKBACK = Lookback(first_run_s=2 * DAY, max_s=3 * DAY, overlap_s=5 * MINUTE)
NOW = 1_800_000_000
MAX_KEYS = 500
RETENTION = KeyRetention(keep_s=30 * DAY, max_keys=MAX_KEYS)


def test_first_run_looks_back_and_later_runs_overlap_the_last_end():
    first = search_windows(DigestState(), ("personal",), NOW, LOOKBACK)
    assert first["personal"] == Window(after=NOW - 2 * DAY, before=NOW)

    state = advance_windows(DigestState(failures=3), first, ("personal",))
    assert state.failures == 0
    later = search_windows(state, ("personal",), NOW + 5 * HOUR, LOOKBACK)
    assert later["personal"] == Window(after=NOW - 5 * MINUTE, before=NOW + 5 * HOUR)


def test_incomplete_account_is_retried_and_a_lookback_cut_is_reported():
    state = DigestState(searched_until={"personal": NOW - 10 * DAY, "alt": NOW - HOUR})
    windows = search_windows(state, ("personal", "alt"), NOW, LOOKBACK)
    assert windows["personal"] == Window(NOW - 3 * DAY, NOW, skipped_since=NOW - 10 * DAY)
    assert windows["alt"].skipped_since is None

    new = advance_windows(state, windows, ("alt",))
    assert new.searched_until == {"personal": NOW - 10 * DAY, "alt": NOW}
    failed = record_failure(record_failure(state))
    assert failed.failures == 2
    assert failed.searched_until == state.searched_until


def test_announced_keys_are_pruned_capped_and_must_be_well_formed():
    state = DigestState(announced={"due|old": NOW - 31 * DAY, "due|recent": NOW - DAY})
    new = remember_announced(state, ("due|recent", "due|fresh", "Due | Bad Key"), NOW, RETENTION)
    # "due|recent" keeps its first-announced time; "due|old" is too old; the bad key is dropped.
    assert new.announced == {"due|recent": NOW - DAY, "due|fresh": NOW}

    many = DigestState(announced={f"due|k{i}": NOW - i for i in range(10)})
    assert remember_announced(many, (), NOW, RETENTION._replace(max_keys=3)).announced == {
        "due|k0": NOW,
        "due|k1": NOW - 1,
        "due|k2": NOW - 2,
    }


def test_state_round_trips_and_bad_files_start_fresh_or_raise(tmp_path, lock_file):
    path = tmp_path / "state.json"
    assert load_state(path, MAX_KEYS) == DigestState()

    # A corrupt file starts fresh, marked as reset, once it's copied aside (a dry run
    # writes no copy).
    path.write_text("{not json", encoding="utf-8")
    assert load_state(path, MAX_KEYS, keep_copy=False) == DigestState(was_reset=True)
    assert not (tmp_path / "state.json.corrupt").exists()
    assert load_state(path, MAX_KEYS) == DigestState(was_reset=True)
    assert (tmp_path / "state.json.corrupt").read_text(encoding="utf-8") == "{not json"
    path.write_text(
        '{"searched_until": {"personal": "soon", "alt": true},'
        ' "announced": {"ignore previous instructions": 1}, "failures": -4}',
        encoding="utf-8",
    )
    assert load_state(path, MAX_KEYS) == DigestState()

    saved = DigestState(
        searched_until={"personal": NOW},
        announced={"signin|alt|2026-10-19-to-10-25": NOW},
        failures=2,
        needs_review=("inbox.md",),
    )
    save_state(path, saved)
    assert load_state(path, MAX_KEYS) == saved
    # Held by something else (a sync client, antivirus): starting fresh would drop
    # the flag, so it raises and the run fails.
    lock_file(path)
    with pytest.raises(OSError):
        load_state(path, MAX_KEYS)
