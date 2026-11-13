"""Tests for the voice notes' wording. Delivery is tested in packages/hubnotify."""

from signal_hub_notify import HubNote

from claude_sessions.notify import (
    approval_needed_note,
    session_failed_note,
    source_for,
    turn_finished_note,
)


def test_turn_finished_note_reads_the_first_two_sentences() -> None:
    reply = "All tests pass.  I pushed the fix to main!\nNext I would look at the CI cache. Bye."

    note = turn_finished_note("OtherRepo", reply)

    assert note == HubNote(
        "session:OtherRepo",
        "OtherRepo session finished: All tests pass. I pushed the fix to main!",
        "normal",
    )
    assert turn_finished_note("OtherRepo", "").text == "OtherRepo session finished."


def test_approval_and_failure_notes_are_high_priority() -> None:
    approval = approval_needed_note("KeyForge", "Claude wants to run git push.\ngit push --force")
    failure = session_failed_note("KeyForge", "the Claude CLI exited")

    assert approval.priority == failure.priority == "high"
    # Only the headline is spoken; the raw command stays in the dialog.
    assert approval.text == (
        "KeyForge session needs approval: Claude wants to run git push. "
        "Answer the dialog on the PC."
    )
    assert failure.text == "KeyForge session hit an error: the Claude CLI exited"
    assert len(source_for("x" * 100)) == 64
