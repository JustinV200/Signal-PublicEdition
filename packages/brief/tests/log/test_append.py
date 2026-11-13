"""Tests for appending: refs and unseen entries through compaction, folding, the entry checks."""

from datetime import timedelta

import pytest
from support import UNDO, at, log, make_paths

from signal_brief import NewEntry, append_entry, current_entries, resolve_entry
from signal_brief.log import advance_through_locked


def test_compaction_keeps_refs_stable_and_unseen_entries_however_old(tmp_path) -> None:
    paths = make_paths(tmp_path)
    start = at(1, 9)
    old_done = log(paths, "done", "Old cleanup", start, key="cleanup")
    advance_through_locked(paths, old_done.seq)  # the owner was briefed on the cleanup only
    wait = log(paths, "waiting", "Approve the purchase", start, key="buy")
    decision = log(paths, "decision", "Picked port 8790", start + timedelta(days=25), key="port")
    auto = log(paths, "new", "Grade posted", start)

    renamed = log(paths, "waiting", "Approve the bigger purchase", start, key="buy")
    same_again = log(paths, "waiting", "Approve the bigger purchase", start, key="buy")
    assert (wait.ref, decision.ref, auto.ref, auto.key) == ("W1", "D1", "N1", "auto:4")
    assert renamed.ref == "W1" and renamed.seq == 5
    assert same_again.seq == 5  # an unchanged re-log isn't rewritten

    # A week on, the append compacts: one line per key, and seen closed keys over 30 days
    # old go. The grade, as old but past the bookmark, stays until the owner's briefed on it.
    later = start + timedelta(days=33)  # a week after the day-25 append compacted
    log(paths, "done", "Old cleanup", later, key="other")
    refs = {entry.key: entry.ref for entry in current_entries(paths)}
    assert "cleanup" not in refs and old_done.ref == "F1"
    # F1 is never handed out again.
    assert refs == {"buy": "W1", "port": "D1", "auto:4": "N1", "other": "F2"}
    assert len(paths.events.read_text().splitlines()) == 4

    resolved = resolve_entry(paths, "w1", later)
    assert (resolved.ref, resolved.resolved) == ("W1", True)


@pytest.mark.parametrize(
    "new",
    [
        NewEntry("new", "Hidden" + chr(0x202E) + "txt.exe"),  # a format character
        NewEntry("new", "Two\nlines"),
        NewEntry("new", "x" * 141),
        NewEntry("new", "Bad key", key="Has Caps"),
        NewEntry("decision", "Chose something"),  # a decision needs an undo
        NewEntry("heads_up", "From mail", undo=UNDO, untrusted=True),
        NewEntry("done", "Odd undo", undo={"tool": "rm -rf", "args": {}}),
    ],
)
def test_bad_entries_are_refused(tmp_path, new) -> None:
    with pytest.raises(ValueError):
        append_entry(make_paths(tmp_path), new, at(20, 9))


def test_detail_may_have_line_breaks(tmp_path) -> None:
    entry = log(make_paths(tmp_path), "new", "Notes", at(20, 9), detail="one\ntwo")
    assert entry.content.detail == "one\ntwo"
